"""Routes REST des annonces (préfixe ``/api/annonces``).

Les routes se limitent à valider l'entrée, vérifier les droits, appeler le service et sérialiser
la réponse ; la logique métier est dans ``app.services.annonce_service``.

Droits (USER-002) :
- lecture publique : seules les annonces **publiées** sont visibles ; le propriétaire voit aussi les siennes ;
- création : propriétaires connectés uniquement (``owner_id`` = compte connecté) ;
- modification, suppression, statut, photos : propriétaire de l'annonce uniquement (403 sinon).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, get_current_user, jwt_required, verify_jwt_in_request
from sqlalchemy import func, select
from werkzeug.exceptions import NotFound

from app.errors import Interdit
from app.ia import estimation_prix
from app import db
from app.ia.fiabilite.service import (analyser_annonce, identifiants_photos_en_cause,
                                     liste_publique_doublons)
from app.models import (ActionHistorique, Annonce, AnnonceControleFiabilite, AnnonceHistorique, RoleUtilisateur,
                        DisponibiliteVisite, StatutAnnonce, StatutVisite, Utilisateur, Visite)
from app.schemas.annonce_schema import (
    AnnonceCreateSchema,
    AnnonceFiltreSchema,
    AnnonceStatutSchema,
    AnnonceUpdateSchema,
    DemandeRevueSchema,
    PhotoOrdreSchema,
)
from app.securite import MESSAGE_RESERVE_PROPRIETAIRES, proprietaire_requis, utilisateur_optionnel
from app.services import annonce_service, photo_service
from app.services.historique_service import enregistrer_action
from app.services.planification_absence import charger_ou_entrainer
from app.services.planification_visites import proposer_creneaux, statuts_bloquants

bp = Blueprint("annonces", __name__, url_prefix="/api/annonces")

MESSAGE_PAS_PROPRIETAIRE = "Vous ne pouvez modifier que vos propres annonces."

_create_schema = AnnonceCreateSchema()
_update_schema = AnnonceUpdateSchema()
_statut_schema = AnnonceStatutSchema()
_filtre_schema = AnnonceFiltreSchema()
_ordre_schema = PhotoOrdreSchema()
_demande_revue_schema = DemandeRevueSchema()


def _annonce_du_proprietaire(annonce_id: int) -> Annonce:
    """Renvoie l'annonce si elle appartient au compte connecté.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        Annonce: L'annonce.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas (404).
        Interdit: Si elle appartient à un autre compte (403).
    """
    annonce = annonce_service.obtenir_annonce(annonce_id)
    if annonce.owner_id != current_user.id:
        raise Interdit(MESSAGE_PAS_PROPRIETAIRE)
    return annonce


def _proprietaire_connecte() -> Utilisateur:
    """Compte connecté, s'il est propriétaire.

    Returns:
        Utilisateur: Le compte connecté.

    Raises:
        Interdit: Si le compte n'est pas propriétaire (403) ; 401 si personne n'est connecté.
    """
    verify_jwt_in_request()
    if current_user.role != RoleUtilisateur.PROPRIETAIRE:
        raise Interdit(MESSAGE_RESERVE_PROPRIETAIRES)
    return get_current_user()


def _ajouter_positions_marche(annonces: list[dict[str, Any]]) -> None:
    """Ajoute à chaque annonce publique sa position par rapport au marché estimé (badge « bonne affaire »).

    Une panne du modèle ne doit jamais empêcher d'afficher les annonces : en cas d'erreur, pas de badge.

    Args:
        annonces: Annonces sérialisées, complétées sur place (clé ``marche``, ou ``None``).
    """
    try:
        positions = estimation_prix.positions_marche(annonces, Path(current_app.config["MODELES_FOLDER"]))
    except Exception:  # noqa: BLE001 — l'IA est un bonus : on journalise et on affiche les annonces sans badge
        current_app.logger.exception("Calcul des positions de marché impossible")
        positions = {}
    for annonce in annonces:
        annonce["marche"] = positions.get(annonce["id"])


@bp.get("")
def lister() -> ResponseReturnValue:
    """Liste les annonces avec filtres optionnels et pagination.

    Sans ``mes_annonces`` : catalogue public, annonces publiées uniquement (même pour un compte connecté).
    Avec ``mes_annonces=true`` : toutes les annonces du propriétaire connecté (401 / 403 sinon).

    Returns:
        ResponseReturnValue: 200 avec ``items``, ``page``, ``per_page``, ``total`` ; 400, 401 ou 403.
    """
    params = _filtre_schema.load(request.args)
    page = params.pop("page")
    per_page = params.pop("per_page")
    tri = params.pop("tri")
    owner_id = _proprietaire_connecte().id if params.pop("mes_annonces") else None
    resultat = annonce_service.lister_annonces(
        params, page, per_page, owner_id=owner_id, tri=tri,
        dossier_modeles=Path(current_app.config["MODELES_FOLDER"]),
    )
    if owner_id is None:  # catalogue public : badge « prix sous / dans / au-dessus du marché »
        _ajouter_positions_marche(resultat["items"])
    else:
        for item in resultat["items"]:
            annonce = db.session.get(Annonce, item["id"])
            controle = db.session.scalar(select(AnnonceControleFiabilite).where(
                AnnonceControleFiabilite.annonce_id == item["id"]
            ))
            item["motif_attente"] = annonce.motif_attente
            item["revue_demandee_le"] = annonce.revue_demandee_le.isoformat() if annonce.revue_demandee_le else None
            item["fiabilite"] = _vue_proprietaire(controle) if controle else None
    return jsonify(resultat), 200


@bp.get("/<int:annonce_id>")
def detail(annonce_id: int) -> ResponseReturnValue:
    """Renvoie le détail d'une annonce publiée, ou d'une annonce du propriétaire connecté.

    Une annonce non publiée est introuvable (404) pour les autres, pour ne pas révéler qu'elle existe.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 200 avec l'annonce, ou 404.
    """
    annonce = annonce_service.obtenir_annonce(annonce_id)
    utilisateur = utilisateur_optionnel()
    if annonce.statut != StatutAnnonce.PUBLIEE:
        if utilisateur is None or utilisateur.id != annonce.owner_id:
            raise NotFound(f"Annonce {annonce_id} introuvable")
    donnees = annonce.to_dict()
    if (
        utilisateur is not None
        and annonce.owner_id == utilisateur.id
        and (annonce.motif_attente is not None or annonce.revue_demandee_le is not None)
    ):
        donnees["motif_attente"] = annonce.motif_attente
        donnees["revue_demandee_le"] = annonce.revue_demandee_le.isoformat() if annonce.revue_demandee_le else None
    if request.args.get("inclure_disponibilites") == "true" and utilisateur and annonce.owner_id == utilisateur.id:
        donnees["disponibilites"] = [
            item.to_dict() for item in db.session.scalars(
                select(DisponibiliteVisite).where(DisponibiliteVisite.annonce_id == annonce.id)
            ).all()
        ]
    if annonce.statut == StatutAnnonce.PUBLIEE:
        _ajouter_positions_marche([donnees])
    return jsonify(donnees), 200


@bp.get("/<int:annonce_id>/creneaux")
def creneaux(annonce_id: int) -> ResponseReturnValue:
    """Propose les trois meilleurs créneaux libres pour une annonce publiée."""
    annonce = annonce_service.obtenir_annonce(annonce_id)
    if annonce.statut != StatutAnnonce.PUBLIEE:
        raise NotFound(f"Annonce {annonce_id} introuvable")
    disponibilites = db.session.scalars(
        select(DisponibiliteVisite).where(DisponibiliteVisite.annonce_id == annonce.id)
    ).all()
    visites = db.session.scalars(
        select(Visite).where(
            Visite.proprietaire_id == annonce.owner_id,
            Visite.statut.in_(statuts_bloquants()),
            Visite.date_visite >= datetime.now(timezone.utc).date(),
        )
    ).all()
    visiteur = utilisateur_optionnel()
    absences_passees = 0
    if visiteur is not None:
        absences_passees = db.session.scalar(
            select(func.count()).select_from(Visite).where(
                Visite.client_id == visiteur.id,
                Visite.statut == StatutVisite.ABSENT,
            )
        ) or 0
    predicteur = charger_ou_entrainer()
    propositions = proposer_creneaux(
        annonce, disponibilites, visites, predicteur=predicteur,
        absences_passees=absences_passees,
    )
    return jsonify({
        "annonce_id": annonce.id,
        "titre": annonce.titre,
        "creneaux": [proposition.to_dict() for proposition in propositions],
    }), 200


@bp.put("/<int:annonce_id>/disponibilites-visite")
@jwt_required()
def modifier_disponibilites_visite(annonce_id: int) -> ResponseReturnValue:
    """Remplace les disponibilités de visite d'une annonce du propriétaire."""
    annonce = _annonce_du_proprietaire(annonce_id)
    donnees = request.get_json() or {}
    disponibilites = donnees.get("disponibilites", [])
    if not isinstance(disponibilites, list) or len(disponibilites) > 7:
        return jsonify(error="validation", message="Les disponibilités sont invalides."), 400

    validees: list[DisponibiliteVisite] = []
    try:
        for item in disponibilites:
            jour = int(item["jour_semaine"])
            debut = str(item["heure_debut"])
            fin = str(item["heure_fin"])
            if jour < 1 or jour > 7 or len(debut) != 5 or len(fin) != 5:
                raise ValueError
            debut_minutes = int(debut[:2]) * 60 + int(debut[3:])
            fin_minutes = int(fin[:2]) * 60 + int(fin[3:])
            if (
                debut_minutes >= fin_minutes
                or not 0 <= debut_minutes < 24 * 60
                or not 0 < fin_minutes <= 24 * 60
                or debut[2] != ":" or fin[2] != ":"
            ):
                raise ValueError
            validees.append(DisponibiliteVisite(
                annonce_id=annonce.id, jour_semaine=jour,
                heure_debut=debut, heure_fin=fin, actif=True,
            ))
    except (KeyError, TypeError, ValueError):
        return jsonify(error="validation", message="Chaque disponibilité doit contenir un jour et un horaire valide."), 400

    db.session.query(DisponibiliteVisite).filter_by(annonce_id=annonce.id).delete()
    db.session.add_all(validees)
    db.session.commit()
    return jsonify({"disponibilites": [item.to_dict() for item in validees]}), 200


@bp.get("/<int:annonce_id>/disponibilites-visite")
def obtenir_disponibilites_visite(annonce_id: int) -> ResponseReturnValue:
    """Renvoie les disponibilités publiques nécessaires au calcul des créneaux."""
    annonce = annonce_service.obtenir_annonce(annonce_id)
    if annonce.statut != StatutAnnonce.PUBLIEE:
        utilisateur = utilisateur_optionnel()
        if utilisateur is None or utilisateur.id != annonce.owner_id:
            raise NotFound(f"Annonce {annonce_id} introuvable")
    disponibilites = db.session.scalars(
        select(DisponibiliteVisite).where(DisponibiliteVisite.annonce_id == annonce.id)
    ).all()
    return jsonify({"disponibilites": [item.to_dict() for item in disponibilites]}), 200


@bp.post("")
@proprietaire_requis
def creer() -> ResponseReturnValue:
    """Crée une annonce pour le propriétaire connecté.

    Returns:
        ResponseReturnValue: 201 avec l'annonce créée, 400, 401 ou 403.
    """
    donnees = _create_schema.load(request.get_json())
    return jsonify(annonce_service.creer_annonce(donnees, owner_id=current_user.id).to_dict()), 201


@bp.put("/<int:annonce_id>")
@jwt_required()
def modifier(annonce_id: int) -> ResponseReturnValue:
    """Modifie une annonce du propriétaire connecté (seuls les champs envoyés sont mis à jour).

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 200 avec l'annonce modifiée, 400, 401, 403 ou 404.
    """
    _annonce_du_proprietaire(annonce_id)
    donnees = _update_schema.load(request.get_json(), partial=True)
    annonce = annonce_service.modifier_annonce(annonce_id, donnees)
    resultat = _recontroler_apres_tentative(annonce, changement="champs:" + ",".join(sorted(donnees)))
    return jsonify({**annonce.to_dict(), **(resultat or {})}), 200


@bp.delete("/<int:annonce_id>")
@jwt_required()
def supprimer(annonce_id: int) -> ResponseReturnValue:
    """Supprime une annonce du propriétaire connecté et ses photos.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 204 sans contenu, 401, 403 ou 404.
    """
    _annonce_du_proprietaire(annonce_id)
    annonce_service.supprimer_annonce(annonce_id)
    return "", 204


@bp.patch("/<int:annonce_id>/statut")
@jwt_required()
def changer_statut(annonce_id: int) -> ResponseReturnValue:
    """Change le statut d'une annonce du propriétaire connecté.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 200 avec l'annonce mise à jour, 400, 401, 403 ou 404.
    """
    donnees = _statut_schema.load(request.get_json())
    annonce = _annonce_du_proprietaire(annonce_id)
    statut = donnees["statut"]
    if statut != StatutAnnonce.PUBLIEE:
        if annonce.statut == StatutAnnonce.EN_ATTENTE and annonce.motif_attente == "fiabilite":
            return jsonify(message="Le statut ne peut pas être changé pendant la vérification."), 403
        return jsonify(annonce_service.changer_statut(annonce_id, statut).to_dict()), 200
    if annonce.statut == StatutAnnonce.PUBLIEE:
        return jsonify(annonce.to_dict()), 200
    if annonce.statut == StatutAnnonce.EN_ATTENTE and annonce.motif_attente == "fiabilite":
        return jsonify(message="Le statut ne peut pas être changé pendant la vérification."), 403

    statut_initial = annonce.statut
    resultat = analyser_annonce(annonce, Path(current_app.config["MODELES_FOLDER"]))
    db.session.refresh(annonce)
    if annonce.statut != statut_initial:
        return jsonify(message="L’annonce a changé pendant le contrôle. Actualisez la page."), 409
    controle = db.session.scalar(select(AnnonceControleFiabilite).where(
        AnnonceControleFiabilite.annonce_id == annonce.id
    ))
    champs = {
        "niveau": resultat["niveau"], "score": resultat["score"], "raisons": resultat["raisons"],
        "doublons": resultat["doublons"], "decision": resultat["decision"],
        "modele_texte": resultat["modele_texte"], "version": resultat["version"],
    }
    if controle is None:
        controle = AnnonceControleFiabilite(annonce_id=annonce.id, **champs)
        db.session.add(controle)
    else:
        for cle, valeur in champs.items():
            setattr(controle, cle, valeur)
        controle.calcule_le = datetime.now(timezone.utc)
    db.session.flush()
    vue = _vue_proprietaire(controle)

    photos_detectees = identifiants_photos_en_cause(
        annonce, controle, Path(current_app.config["MODELES_FOLDER"])
    )
    if photos_detectees:
        rangs = [index for index, photo in enumerate(annonce.photos, 1)
                 if photo.id in photos_detectees]
        enregistrer_action(annonce, ActionHistorique.CONTROLE_FIABILITE,
                           {"niveau": resultat["niveau"], "score": resultat["score"],
                            "publication_bloquee_photo": True})
        db.session.commit()
        detail_photos = ", ".join(str(rang) for rang in rangs)
        return jsonify(
            error="photos_deja_utilisees",
            message=("Publication bloquée : une ou plusieurs photos sont déjà utilisées dans une autre annonce. "
                     f"Remplacez la ou les photos n° {detail_photos} par vos propres photos, puis réessayez."),
            photos_a_remplacer=rangs,
        ), 409

    if resultat["niveau"] == "a_verifier":
        annonce.statut = StatutAnnonce.EN_ATTENTE
        annonce.motif_attente = "fiabilite"
        enregistrer_action(annonce, ActionHistorique.CHANGEMENT_STATUT,
                           {"avant": statut_initial.value, "apres": StatutAnnonce.EN_ATTENTE.value})
        enregistrer_action(annonce, ActionHistorique.CONTROLE_FIABILITE,
                           {"niveau": resultat["niveau"], "score": resultat["score"]})
        enregistrer_action(annonce, ActionHistorique.MISE_EN_ATTENTE,
                           {"motif": "fiabilite", "niveau": resultat["niveau"]})
        db.session.commit()
        return jsonify({**annonce.to_dict(), "motif_attente": annonce.motif_attente, "fiabilite": vue}), 200

    if resultat["niveau"] == "a_surveiller" and not donnees["confirmation_fiabilite"]:
        enregistrer_action(annonce, ActionHistorique.CONTROLE_FIABILITE,
                           {"niveau": resultat["niveau"], "score": resultat["score"]})
        db.session.commit()
        return jsonify(error="confirmation_requise", fiabilite=vue), 409

    annonce.statut = StatutAnnonce.PUBLIEE
    annonce.motif_attente = None
    if resultat["niveau"] == "a_surveiller":
        enregistrer_action(annonce, ActionHistorique.CONTROLE_FIABILITE,
                           {"niveau": resultat["niveau"], "score": resultat["score"]})
        enregistrer_action(annonce, ActionHistorique.PUBLICATION_CONFIRMEE,
                           {"niveau": resultat["niveau"], "confirmation_fiabilite": True})
    else:
        enregistrer_action(annonce, ActionHistorique.CHANGEMENT_STATUT,
                           {"avant": statut_initial.value, "apres": StatutAnnonce.PUBLIEE.value})
    db.session.commit()
    return jsonify({**annonce.to_dict(), "motif_attente": annonce.motif_attente, "fiabilite": vue}), 200


def _vue_proprietaire(controle: AnnonceControleFiabilite) -> dict[str, Any]:
    """Sérialise le contrôle propriétaire sans révéler les annonces privées tierces."""
    return {**controle.proprietaire_dict(), "annonces_liees": liste_publique_doublons(controle)}


def _recontroler_apres_tentative(
    annonce: Annonce, changement: str = "annonce"
) -> dict[str, Any] | None:
    """Recalcule le contrôle après modification d'une annonce mise en attente.

    Une annonce qui ne déclenche plus ce niveau revient en brouillon, jamais publiée automatiquement.
    """
    if annonce.statut != StatutAnnonce.EN_ATTENTE or annonce.motif_attente != "fiabilite":
        return None
    controle = db.session.scalar(select(AnnonceControleFiabilite).where(
        AnnonceControleFiabilite.annonce_id == annonce.id
    ))
    dossier_modeles = Path(current_app.config["MODELES_FOLDER"])
    photos_en_cause = identifiants_photos_en_cause(annonce, controle, dossier_modeles)
    nb_tentatives = db.session.scalar(select(db.func.count()).select_from(AnnonceHistorique).where(
        AnnonceHistorique.annonce_id == annonce.id,
        AnnonceHistorique.action == ActionHistorique.NOUVELLE_TENTATIVE,
    )) or 0
    if photos_en_cause:
        enregistrer_action(annonce, ActionHistorique.NOUVELLE_TENTATIVE, {
            "numero": nb_tentatives + 1, "changement": changement,
            "photos_encore_en_cause": photos_en_cause,
        })
        db.session.commit()
        rangs = [next((index for index, photo in enumerate(annonce.photos, 1)
                       if photo.id == photo_id), 0) for photo_id in photos_en_cause]
        rangs = [rang for rang in rangs if rang]
        return {
            "motif_attente": annonce.motif_attente,
            "message_fiabilite": "L'annonce reste en attente : les photos identiques sont toujours présentes.",
            "photos_encore_en_cause": rangs,
            "fiabilite": _vue_proprietaire(controle) if controle else None,
        }

    resultat = analyser_annonce(annonce, dossier_modeles)
    champs = {
        "niveau": resultat["niveau"], "score": resultat["score"], "raisons": resultat["raisons"],
        "doublons": resultat["doublons"], "decision": resultat["decision"],
        "modele_texte": resultat["modele_texte"], "version": resultat["version"],
    }
    if controle is None:
        controle = AnnonceControleFiabilite(annonce_id=annonce.id, **champs)
        db.session.add(controle)
    else:
        for cle, valeur in champs.items():
            setattr(controle, cle, valeur)
        controle.calcule_le = datetime.now(timezone.utc)
    enregistrer_action(annonce, ActionHistorique.NOUVELLE_TENTATIVE,
                       {"numero": nb_tentatives + 1, "changement": changement,
                        "niveau": resultat["niveau"], "score": resultat["score"]})
    if resultat["niveau"] != "a_verifier":
        annonce.statut = StatutAnnonce.BROUILLON
        annonce.motif_attente = None
        annonce.revue_demandee_le = None
        enregistrer_action(annonce, ActionHistorique.ATTENTE_LEVEE,
                           {"motif": "fiabilite", "raison": "modification_proprietaire"})
    db.session.commit()
    message = ("Les photos en cause ont été retirées : vous pouvez publier votre annonce."
               if annonce.motif_attente is None else
               "L'annonce reste en attente de vérification.")
    if annonce.motif_attente is None and resultat["niveau"] == "a_surveiller":
        message = "Les photos en cause ont été retirées. Un point reste à vérifier : la publication demandera une confirmation."
    return {"motif_attente": annonce.motif_attente, "message_fiabilite": message,
            "fiabilite": _vue_proprietaire(controle)}


@bp.get("/<int:annonce_id>/fiabilite")
@proprietaire_requis
def fiabilite(annonce_id: int) -> ResponseReturnValue:
    """Retourne le dernier contrôle uniquement au propriétaire de l'annonce."""
    annonce = _annonce_du_proprietaire(annonce_id)
    controle = db.session.scalar(select(AnnonceControleFiabilite).where(
        AnnonceControleFiabilite.annonce_id == annonce.id
    ))
    return jsonify({"controle": _vue_proprietaire(controle) if controle else None,
                    "motif_attente": annonce.motif_attente,
                    "revue_demandee_le": annonce.revue_demandee_le.isoformat()
                    if annonce.revue_demandee_le else None}), 200


@bp.post("/<int:annonce_id>/fiabilite/revue")
@proprietaire_requis
def demander_revue_fiabilite(annonce_id: int) -> ResponseReturnValue:
    """Enregistre une demande de revue humaine d'une annonce mise en attente."""
    annonce = _annonce_du_proprietaire(annonce_id)
    corps = _demande_revue_schema.load(request.get_json(silent=True) or {})
    if annonce.statut != StatutAnnonce.EN_ATTENTE or annonce.motif_attente != "fiabilite":
        return jsonify(error="revue_indisponible",
                       message="Cette annonce n’est pas en attente de vérification."), 409
    annonce.revue_demandee_le = datetime.now(timezone.utc)
    enregistrer_action(annonce, ActionHistorique.DEMANDE_REVUE,
                       {"message": corps.get("message")} if corps.get("message") else {})
    db.session.commit()
    return jsonify(revue_demandee_le=annonce.revue_demandee_le.isoformat()), 202


@bp.post("/<int:annonce_id>/photos")
@jwt_required()
def ajouter_photos(annonce_id: int) -> ResponseReturnValue:
    """Ajoute 1 à 10 photos (multipart/form-data, champ ``photos``) à une annonce du propriétaire connecté.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 201 avec ``{"photos": [...]}``, 400, 401, 403, 404 ou 413.
    """
    _annonce_du_proprietaire(annonce_id)
    photos = photo_service.ajouter_photos(annonce_id, request.files.getlist("photos"))
    annonce = db.session.get(Annonce, annonce_id)
    resultat = _recontroler_apres_tentative(annonce, changement="photos_ajoutees")
    return jsonify(photos=[photo.to_dict() for photo in photos], **(resultat or {})), 201


@bp.delete("/<int:annonce_id>/photos/<int:photo_id>")
@jwt_required()
def supprimer_photo(annonce_id: int, photo_id: int) -> ResponseReturnValue:
    """Supprime une photo (base et fichier) d'une annonce du propriétaire connecté.

    Args:
        annonce_id: Identifiant de l'annonce.
        photo_id: Identifiant de la photo.

    Returns:
        ResponseReturnValue: 204 sans contenu, 401, 403 ou 404.
    """
    _annonce_du_proprietaire(annonce_id)
    photo_service.supprimer_photo(annonce_id, photo_id)
    annonce = db.session.get(Annonce, annonce_id)
    resultat = _recontroler_apres_tentative(annonce, changement="photo_supprimee")
    return (jsonify(resultat), 200) if resultat else ("", 204)


@bp.patch("/<int:annonce_id>/photos/ordre")
@jwt_required()
def reordonner_photos(annonce_id: int) -> ResponseReturnValue:
    """Réordonne les photos d'une annonce du propriétaire connecté à partir de ``{"ordre": [id, id, ...]}``.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 200 avec ``{"photos": [...]}`` dans le nouvel ordre, 400, 401, 403 ou 404.
    """
    _annonce_du_proprietaire(annonce_id)
    donnees = _ordre_schema.load(request.get_json())
    photos = photo_service.reordonner_photos(annonce_id, donnees["ordre"])
    annonce = db.session.get(Annonce, annonce_id)
    resultat = _recontroler_apres_tentative(annonce, changement="ordre_photos")
    return jsonify(photos=[photo.to_dict() for photo in photos], **(resultat or {})), 200
