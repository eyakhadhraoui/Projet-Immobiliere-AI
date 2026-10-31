"""Routes de gestion des visites (préfixe ``/api/visites``)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (Annonce, CreneauVisiteReserve, DisponibiliteVisite, RechercheVisite,
                        StatutVisite, TypeVisite, Utilisateur, Visite)
from app.models.historique import ActionHistorique, AnnonceHistorique
from app.schemas.recherche_visite_schema import RechercheVisiteSchema
from app.securite import utilisateur_optionnel
from app.services.planification_visites import creneau_autorise, statuts_bloquants
from app.services.recherche_visites import rechercher as rechercher_visites

bp = Blueprint("visites", __name__, url_prefix="/api/visites")


@bp.post("/recherche")
def rechercher_annonces_visite() -> ResponseReturnValue:
    """Recherche les annonces strictement admissibles avec des créneaux compatibles."""
    from marshmallow import ValidationError

    try:
        criteres = RechercheVisiteSchema().load(request.get_json() or {})
    except ValidationError as erreur:
        return jsonify({"error": "validation", "message": "Les critères de recherche sont invalides.",
                        "champs": erreur.messages}), 400

    annonces, modele_utilise = rechercher_visites(criteres, Path(current_app.config["MODELES_FOLDER"]))
    user = utilisateur_optionnel()
    methode = "lightgbm_lambdarank_simule" if modele_utilise else (
        "chronologique_demande" if criteres["tri"] == "chronologique" else "chronologique_repli"
    )
    criteria_json = {
        "villes": criteres["villes"],
        "transaction": criteres["transaction"].value if criteres.get("transaction") else None,
        "type_bien": criteres["type_bien"].value if criteres.get("type_bien") else None,
        "budget_max": criteres.get("budget_max"),
        "pieces_min": criteres.get("pieces_min"),
        "tri_demande": criteres["tri"],
        "disponibilites": [{"debut": item["debut"].isoformat(), "fin": item["fin"].isoformat()}
                            for item in criteres["disponibilites"]],
    }
    recherche = RechercheVisite(
        utilisateur_id=user.id if user else None,
        criteres=criteria_json,
        candidats_annonce_ids=[item["id"] for item in annonces],
        methode_classement=methode,
    )
    db.session.add(recherche)
    db.session.commit()
    return jsonify({
        "recherche_id": recherche.id,
        "items": annonces,
        "total": len(annonces),
        "tri_demande": criteres["tri"],
        "tri_applique": "pertinence" if modele_utilise else "chronologique",
        "methode_classement": methode,
        "origine_donnees_classement": "simulees" if modele_utilise else None,
        "message_classement": (
            "Classement expérimental entraîné sur données simulées; aucun gain sur de vrais visiteurs n'est démontré."
            if modele_utilise else "Tri chronologique demandé."
            if criteres["tri"] == "chronologique" else
            "Classement par date; le modèle LightGBM n'a pas été utilisé."
        ),
    }), 200


def _prochain_numero_visite() -> str:
    """Génère une référence unique type VIS-2026-0001."""
    annee = date.today().year
    nb = db.session.scalar(select(db.func.count(Visite.id))) or 0
    return f"VIS-{annee}-{nb + 1:04d}"


@bp.get("")
def lister_visites() -> ResponseReturnValue:
    """Liste les visites avec recherche textuelle et filtres."""
    user = utilisateur_optionnel()
    owner_id = user.id if user else 1

    recherche = request.args.get("recherche", "").strip()
    statut = request.args.get("statut", "").strip()
    type_v = request.args.get("type_visite", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 15))))

    requete = (
        select(Visite)
        .outerjoin(Annonce, Visite.annonce_id == Annonce.id)
        .outerjoin(Utilisateur, Visite.client_id == Utilisateur.id)
        .order_by(Visite.date_visite.desc(), Visite.heure_debut.desc())
    )

    if statut:
        requete = requete.where(Visite.statut == statut)
    if type_v:
        requete = requete.where(Visite.type_visite == type_v)
    if recherche:
        terme = f"%{recherche}%"
        requete = requete.where(
            or_(
                Visite.reference.ilike(terme),
                Visite.telephone_contact.ilike(terme),
                Annonce.titre.ilike(terme),
                Annonce.ville.ilike(terme),
                Utilisateur.nom.ilike(terme),
                Utilisateur.prenom.ilike(terme),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(requete.subquery())) or 0
    items_db = db.session.scalars(requete.offset((page - 1) * per_page).limit(per_page)).all()

    return jsonify({
        "items": [v.to_dict() for v in items_db],
        "total": total,
        "page": page,
        "per_page": per_page,
    }), 200


@bp.get("/rappels")
def rappels_visites() -> ResponseReturnValue:
    """Renvoie les rappels échus à 24 heures ou 2 heures d'une visite."""
    user = utilisateur_optionnel()
    utilisateur_id = user.id if user else 1
    visites = db.session.scalars(
        select(Visite).where(
            (Visite.client_id == utilisateur_id) | (Visite.proprietaire_id == utilisateur_id),
            Visite.statut.in_(statuts_bloquants()),
        ).order_by(Visite.date_visite, Visite.heure_debut)
    ).all()
    maintenant = datetime.now().astimezone()
    rappels = []
    for visite in visites:
        for rappel in visite.to_dict()["rappels"]:
            date_envoi = datetime.fromisoformat(rappel["date_envoi"])
            if date_envoi <= maintenant and visite.debut_datetime > maintenant:
                rappels.append({
                    "visite_id": visite.id,
                    "reference": visite.reference,
                    "type": rappel["type"],
                    "message": f"Rappel : votre visite « {visite.annonce.titre} » est prévue bientôt.",
                    "date_visite": visite.date_visite.isoformat(),
                    "heure_debut": visite.heure_debut,
                })
    return jsonify({"items": rappels}), 200


@bp.get("/<int:visite_id>")
def detail_visite(visite_id: int) -> ResponseReturnValue:
    """Renvoie le détail d'une visite."""
    visite = db.session.get(Visite, visite_id)
    if not visite:
        return jsonify({"error": "introuvable", "message": "Visite introuvable."}), 404
    return jsonify(visite.to_dict()), 200


@bp.post("")
def creer_visite() -> ResponseReturnValue:
    """Crée une nouvelle visite."""
    donnees = request.get_json() or {}
    annonce_id = donnees.get("annonce_id")
    if not annonce_id:
        # Prendre la première annonce disponible par défaut
        premiere = db.session.scalars(select(Annonce).limit(1)).first()
        if premiere:
            annonce_id = premiere.id

    annonce = db.session.get(Annonce, annonce_id) if annonce_id else None
    if not annonce:
        return jsonify({"error": "validation", "message": "Veuillez associer une annonce existante."}), 400

    user = utilisateur_optionnel()
    client_id = donnees.get("client_id") or (user.id if user else 1)
    proprietaire_id = annonce.owner_id or 1

    recherche_id = donnees.get("recherche_id")
    recherche = None
    if recherche_id is not None:
        if not isinstance(recherche_id, int) or isinstance(recherche_id, bool) or recherche_id < 1:
            return jsonify(error="validation", message="L'identifiant de recherche est invalide."), 400
        recherche = db.session.get(RechercheVisite, recherche_id)
        if not recherche or annonce.id not in recherche.candidats_annonce_ids:
            return jsonify(error="recherche_invalide", message="Cette annonce ne provient pas de cette recherche."), 400
        if recherche.utilisateur_id is not None and (user is None or recherche.utilisateur_id != user.id):
            return jsonify(error="interdit", message="Cette recherche appartient à un autre compte."), 403

    date_str = donnees.get("date_visite")
    if date_str:
        try:
            date_v = date.fromisoformat(str(date_str).split("T")[0])
        except Exception:
            date_v = date.today()
    else:
        date_v = date.today()

    disponibilites = db.session.scalars(
        select(DisponibiliteVisite).where(DisponibiliteVisite.annonce_id == annonce.id)
    ).all()
    if recherche and not any(item.actif for item in disponibilites):
        return jsonify(
            error="creneau_indisponible",
            message="Les disponibilités de cette annonce ont changé. Relancez la recherche.",
        ), 409
    if disponibilites:
        visites_occupees = db.session.scalars(
            select(Visite).where(
                Visite.proprietaire_id == annonce.owner_id,
                Visite.statut.in_(statuts_bloquants()),
                Visite.date_visite == date_v,
            )
        ).all()
        try:
            creneau_valide = creneau_autorise(
                annonce,
                date_v,
                str(donnees.get("heure_debut", "")),
                str(donnees.get("heure_fin", "")),
                disponibilites,
                visites_occupees,
            )
        except ValueError:
            creneau_valide = False
        if not creneau_valide:
            return jsonify(
                error="creneau_indisponible",
                message="Ce créneau n'est plus disponible. Choisissez une autre proposition.",
            ), 409

    visite = Visite(
        reference=_prochain_numero_visite(),
        annonce_id=annonce.id,
        client_id=client_id,
        proprietaire_id=proprietaire_id,
        recherche_id=recherche.id if recherche else None,
        date_visite=date_v,
        heure_debut=donnees.get("heure_debut", "10:00"),
        heure_fin=donnees.get("heure_fin", "11:00"),
        statut=StatutVisite(donnees.get("statut", "en_attente")),
        type_visite=TypeVisite(donnees.get("type_visite", "sur_place")),
        nb_personnes=int(donnees.get("nb_personnes", 1)),
        telephone_contact=donnees.get("telephone_contact") or "98123456",
        message_client=donnees.get("message_client"),
    )
    db.session.add(visite)
    db.session.flush()
    if visite.statut in statuts_bloquants():
        db.session.add(CreneauVisiteReserve(
            annonce_id=annonce.id, date_visite=date_v,
            heure_debut=visite.heure_debut, visite_id=visite.id,
        ))
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return jsonify(
                error="creneau_indisponible",
                message="Ce créneau vient d'être réservé. Choisissez une autre proposition.",
            ), 409

    # Historiser l'action
    historique = AnnonceHistorique(
        annonce_id=annonce.id,
        titre_annonce=annonce.titre,
        action=ActionHistorique.MODIFICATION,
        details={"type": "visite_creee", "reference": visite.reference, "date": visite.date_visite.isoformat()},
        owner_id=proprietaire_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify(visite.to_dict()), 201


@bp.put("/<int:visite_id>")
def modifier_visite(visite_id: int) -> ResponseReturnValue:
    """Met à jour une visite (statut, feedback, date/heure, motif...)."""
    visite = db.session.get(Visite, visite_id)
    if not visite:
        return jsonify({"error": "introuvable", "message": "Visite introuvable."}), 404

    donnees = request.get_json() or {}
    ancien_statut = visite.statut.value if hasattr(visite.statut, "value") else str(visite.statut)

    if "statut" in donnees:
        visite.statut = StatutVisite(donnees["statut"])
        if visite.statut == StatutVisite.CONFIRMEE and not visite.date_confirmation:
            visite.date_confirmation = datetime.now()

    if "date_visite" in donnees and donnees["date_visite"]:
        try:
            visite.date_visite = date.fromisoformat(str(donnees["date_visite"]).split("T")[0])
        except Exception:
            pass
    if "heure_debut" in donnees:
        visite.heure_debut = donnees["heure_debut"]
    if "heure_fin" in donnees:
        visite.heure_fin = donnees["heure_fin"]
    if "type_visite" in donnees:
        visite.type_visite = TypeVisite(donnees["type_visite"])
    if "nb_personnes" in donnees:
        visite.nb_personnes = int(donnees["nb_personnes"])
    if "telephone_contact" in donnees:
        visite.telephone_contact = donnees["telephone_contact"]
    if "message_client" in donnees:
        visite.message_client = donnees["message_client"]
    if "motif_refus" in donnees:
        visite.motif_refus = donnees["motif_refus"]
    if "feedback_client" in donnees:
        visite.feedback_client = donnees["feedback_client"]
    if "note_visite" in donnees:
        visite.note_visite = int(donnees["note_visite"]) if donnees["note_visite"] is not None else None

    # Historiser si changement de statut
    nouveau_statut = visite.statut.value if hasattr(visite.statut, "value") else str(visite.statut)
    if ancien_statut != nouveau_statut and visite.annonce:
        historique = AnnonceHistorique(
            annonce_id=visite.annonce_id,
            titre_annonce=visite.annonce.titre,
            action=ActionHistorique.CHANGEMENT_STATUT,
            details={"type": "visite_statut", "reference": visite.reference, "avant": ancien_statut, "apres": nouveau_statut},
            owner_id=visite.proprietaire_id,
        )
        db.session.add(historique)

    verrou = db.session.scalar(select(CreneauVisiteReserve).where(
        CreneauVisiteReserve.visite_id == visite.id
    ))
    if visite.statut in statuts_bloquants():
        if verrou is None:
            verrou = CreneauVisiteReserve(
                annonce_id=visite.annonce_id, date_visite=visite.date_visite,
                heure_debut=visite.heure_debut, visite_id=visite.id,
            )
            db.session.add(verrou)
        else:
            verrou.annonce_id = visite.annonce_id
            verrou.date_visite = visite.date_visite
            verrou.heure_debut = visite.heure_debut
    elif verrou is not None:
        db.session.delete(verrou)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            error="creneau_indisponible",
            message="Ce créneau vient d'être réservé. Choisissez une autre proposition.",
        ), 409
    return jsonify(visite.to_dict()), 200


@bp.delete("/<int:visite_id>")
def supprimer_visite(visite_id: int) -> ResponseReturnValue:
    """Supprime une visite après confirmation."""
    visite = db.session.get(Visite, visite_id)
    if not visite:
        return jsonify({"error": "introuvable", "message": "Visite introuvable."}), 404

    ref = visite.reference
    annonce_id = visite.annonce_id
    titre_annonce = visite.annonce.titre if visite.annonce else "Annonce"
    owner_id = visite.proprietaire_id

    db.session.execute(db.delete(CreneauVisiteReserve).where(
        CreneauVisiteReserve.visite_id == visite.id
    ))
    db.session.delete(visite)
    historique = AnnonceHistorique(
        annonce_id=annonce_id,
        titre_annonce=titre_annonce,
        action=ActionHistorique.SUPPRESSION,
        details={"type": "visite_supprimee", "reference": ref},
        owner_id=owner_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify({"message": f"Visite {ref} supprimée avec succès."}), 200
