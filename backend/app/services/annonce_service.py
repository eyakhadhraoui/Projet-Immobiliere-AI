"""Logique métier des annonces : CRUD, filtres et pagination.

Chaque action qui modifie une annonce enregistre une entrée d'historique dans la même
transaction (un seul ``commit``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app import db
from app.models import ActionHistorique, Annonce, StatutAnnonce
from app.ia.classement_annonces import classer as classer_annonces
from app.services.historique_service import differences, enregistrer_action

PER_PAGE_DEFAUT = 10
PER_PAGE_MAX = 50


def lister_annonces(
    filtres: dict[str, Any],
    page: int = 1,
    per_page: int = PER_PAGE_DEFAUT,
    owner_id: int | None = None,
    tri: str = "chronologique",
    dossier_modeles: Any = None,
) -> dict[str, Any]:
    """Liste les annonces filtrées, paginées, de la plus récente à la plus ancienne.

    Args:
        filtres: Filtres optionnels déjà validés (``ville``, ``type_bien``,
            ``transaction``, ``prix_min``, ``prix_max``, ``surface_min``,
            ``meuble``, ``statut``).
        page: Numéro de page, à partir de 1.
        per_page: Nombre d'annonces par page, ramené à ``PER_PAGE_MAX`` au plus.
        owner_id: Annonces de ce propriétaire (tous statuts) ; si ``None``, catalogue public :
            **uniquement les annonces publiées**, quel que soit le filtre ``statut``.

    Returns:
        dict[str, Any]: ``items`` (annonces sérialisées), ``page``, ``per_page`` et ``total``.
    """
    per_page = min(per_page, PER_PAGE_MAX)
    requete = select(Annonce)
    if owner_id is not None:
        requete = requete.where(Annonce.owner_id == owner_id)
    else:
        requete = requete.where(Annonce.statut == StatutAnnonce.PUBLIEE)

    if (ville := filtres.get("ville")) is not None:
        requete = requete.where(Annonce.ville.icontains(ville, autoescape=True))
    if (type_bien := filtres.get("type_bien")) is not None:
        requete = requete.where(Annonce.type_bien == type_bien)
    if (transaction := filtres.get("transaction")) is not None:
        requete = requete.where(Annonce.transaction == transaction)
    if (statut := filtres.get("statut")) is not None:
        requete = requete.where(Annonce.statut == statut)
    if (prix_min := filtres.get("prix_min")) is not None:
        requete = requete.where(Annonce.prix >= prix_min)
    if (prix_max := filtres.get("prix_max")) is not None:
        requete = requete.where(Annonce.prix <= prix_max)
    if (surface_min := filtres.get("surface_min")) is not None:
        requete = requete.where(Annonce.surface >= surface_min)
    if (meuble := filtres.get("meuble")) is not None:
        requete = requete.where(Annonce.meuble == meuble)

    requete = requete.order_by(Annonce.created_at.desc(), Annonce.id.desc())
    if tri == "pertinence" and owner_id is None:
        annonces = [annonce.to_dict() for annonce in db.session.scalars(requete).all()]
        annonces, modele_disponible = classer_annonces(annonces, filtres, dossier_modeles)
        debut = (page - 1) * per_page
        resultat = {
            "items": annonces[debut:debut + per_page], "page": page,
            "per_page": per_page, "total": len(annonces),
            "tri_demande": "pertinence",
            "tri_applique": "pertinence" if modele_disponible else "chronologique",
        }
        if not modele_disponible:
            resultat["message_classement"] = (
                "Le classement intelligent est indisponible; les annonces restent classées par date."
            )
        return resultat

    pagination = db.paginate(requete, page=page, per_page=per_page, error_out=False)

    return {
        "items": [annonce.to_dict() for annonce in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    }


def obtenir_annonce(annonce_id: int) -> Annonce:
    """Récupère une annonce par son identifiant.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        Annonce: L'annonce trouvée.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
    """
    return db.get_or_404(Annonce, annonce_id, description=f"Annonce {annonce_id} introuvable")


def creer_annonce(donnees: dict[str, Any], owner_id: int) -> Annonce:
    """Crée une annonce, toujours au statut ``brouillon``.

    Args:
        donnees: Champs validés par ``AnnonceCreateSchema``.
        owner_id: Propriétaire connecté.

    Returns:
        Annonce: L'annonce enregistrée.
    """
    annonce = Annonce(**donnees, owner_id=owner_id, statut=StatutAnnonce.BROUILLON)
    db.session.add(annonce)
    db.session.flush()  # attribue l'identifiant, nécessaire à l'historique
    enregistrer_action(annonce, ActionHistorique.CREATION, {
        "statut": annonce.statut.value,
        "type_bien": annonce.type_bien.value,
        "transaction": annonce.transaction.value,
        "prix": annonce.prix,
        "ville": annonce.ville,
    })
    db.session.commit()
    return annonce


def modifier_annonce(annonce_id: int, donnees: dict[str, Any]) -> Annonce:
    """Modifie les champs fournis d'une annonce.

    L'historique ne retient que les champs dont la valeur change réellement
    (aucune entrée si rien ne change).

    Args:
        annonce_id: Identifiant de l'annonce.
        donnees: Champs validés par ``AnnonceUpdateSchema`` (chargement partiel).

    Returns:
        Annonce: L'annonce modifiée.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
    """
    annonce = obtenir_annonce(annonce_id)
    modifications = differences(annonce, donnees)
    for champ, valeur in donnees.items():
        setattr(annonce, champ, valeur)
    if modifications:
        enregistrer_action(annonce, ActionHistorique.MODIFICATION, modifications)
    db.session.commit()
    return annonce


def supprimer_annonce(annonce_id: int) -> None:
    """Supprime une annonce, ses photos en base, puis leurs fichiers sur le disque.

    L'historique de l'annonce est conservé, avec une entrée « suppression ».

    Args:
        annonce_id: Identifiant de l'annonce.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
    """
    from app.services.photo_service import supprimer_fichiers  # import local : évite un import circulaire

    annonce = obtenir_annonce(annonce_id)
    urls = preparer_suppression(annonce)
    db.session.commit()
    supprimer_fichiers(urls)


def preparer_suppression(annonce: Annonce) -> list[str]:
    """Ajoute à la session la suppression d'une annonce et son entrée d'historique, sans commit.

    Permet de supprimer plusieurs annonces dans une seule transaction (ex. suppression d'un compte
    propriétaire). Les fichiers des photos sont à supprimer par l'appelant, après le commit.

    Args:
        annonce: Annonce à supprimer.

    Returns:
        list[str]: URL des photos de l'annonce.
    """
    urls = [photo.url for photo in annonce.photos]
    enregistrer_action(annonce, ActionHistorique.SUPPRESSION, {
        "statut": annonce.statut.value,
        "nb_photos": len(urls),
    })
    db.session.delete(annonce)
    return urls


def changer_statut(annonce_id: int, statut: StatutAnnonce) -> Annonce:
    """Change le statut d'une annonce (historique enregistré seulement s'il change).

    Args:
        annonce_id: Identifiant de l'annonce.
        statut: Nouveau statut.

    Returns:
        Annonce: L'annonce mise à jour.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
    """
    annonce = obtenir_annonce(annonce_id)
    ancien = annonce.statut
    annonce.statut = statut
    if ancien != statut:
        enregistrer_action(annonce, ActionHistorique.CHANGEMENT_STATUT, {
            "avant": ancien.value,
            "apres": statut.value,
        })
    db.session.commit()
    return annonce
