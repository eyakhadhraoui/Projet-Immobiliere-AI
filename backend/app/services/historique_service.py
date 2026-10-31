"""Historique des actions sur les annonces : enregistrement et consultation.

``enregistrer_action`` ajoute l'entrée à la session sans la valider : le service appelant
fait un seul ``commit`` pour l'action et son historique (même transaction, tout ou rien).
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select

from app import db
from app.models import ActionHistorique, Annonce, AnnonceHistorique

PER_PAGE_DEFAUT = 20
PER_PAGE_MAX = 100


def valeur_json(valeur: Any) -> Any:
    """Convertit une valeur de modèle en valeur JSON (les Enum deviennent leur valeur).

    Args:
        valeur: Valeur d'un attribut d'annonce.

    Returns:
        Any: Valeur sérialisable en JSON.
    """
    if isinstance(valeur, enum.Enum):
        return valeur.value
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, list):
        return [valeur_json(element) for element in valeur]
    return valeur


def differences(objet: Any, donnees: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compare les nouvelles valeurs aux valeurs actuelles d'un objet (annonce, utilisateur…).

    Args:
        objet: Modèle avant modification.
        donnees: Nouvelles valeurs (champs validés).

    Returns:
        dict[str, dict[str, Any]]: ``{champ: {"avant": ..., "apres": ...}}`` pour les seuls
        champs dont la valeur change réellement.
    """
    resultat: dict[str, dict[str, Any]] = {}
    for champ, nouvelle in donnees.items():
        avant, apres = valeur_json(getattr(objet, champ)), valeur_json(nouvelle)
        if avant != apres:
            resultat[champ] = {"avant": avant, "apres": apres}
    return resultat


def enregistrer_action(
    annonce: Annonce, action: ActionHistorique, details: dict[str, Any] | None = None
) -> AnnonceHistorique:
    """Ajoute une entrée d'historique à la session courante, sans commit.

    Args:
        annonce: Annonce concernée (doit déjà avoir un identifiant : ``flush`` si besoin).
        action: Type d'action.
        details: Données propres à l'action.

    Returns:
        AnnonceHistorique: L'entrée ajoutée à la session.
    """
    entree = AnnonceHistorique(
        annonce_id=annonce.id,
        titre_annonce=annonce.titre,
        action=action,
        details=details or {},
        owner_id=annonce.owner_id,
    )
    db.session.add(entree)
    return entree


def _debut_du_jour(jour: date) -> datetime:
    """Début d'une journée (UTC, sans fuseau, comme les dates stockées par SQLite).

    Args:
        jour: Date.

    Returns:
        datetime: ``jour`` à 00:00:00.
    """
    return datetime.combine(jour, time.min)


def lister_historique(
    filtres: dict[str, Any], owner_id: int, page: int = 1, per_page: int = PER_PAGE_DEFAUT
) -> dict[str, Any]:
    """Liste l'historique d'un propriétaire, filtré et paginé, de l'action la plus récente à la plus ancienne.

    Args:
        owner_id: Propriétaire connecté (seules ses annonces, même supprimées).
        filtres: Filtres optionnels déjà validés : ``annonce_id``, ``action``,
            ``date_debut`` et ``date_fin`` (dates incluses, journées UTC).
        page: Numéro de page, à partir de 1.
        per_page: Nombre d'entrées par page, ramené à ``PER_PAGE_MAX`` au plus.

    Returns:
        dict[str, Any]: ``items``, ``page``, ``per_page`` et ``total``.
    """
    per_page = min(per_page, PER_PAGE_MAX)
    requete = select(AnnonceHistorique).where(AnnonceHistorique.owner_id == owner_id)

    if (annonce_id := filtres.get("annonce_id")) is not None:
        requete = requete.where(AnnonceHistorique.annonce_id == annonce_id)
    if (recherche := filtres.get("recherche")):
        requete = requete.where(AnnonceHistorique.titre_annonce.ilike(f"%{recherche.strip()}%"))
    if (action := filtres.get("action")) is not None:
        requete = requete.where(AnnonceHistorique.action == action)
    if (date_debut := filtres.get("date_debut")) is not None:
        requete = requete.where(AnnonceHistorique.created_at >= _debut_du_jour(date_debut))
    if (date_fin := filtres.get("date_fin")) is not None:
        requete = requete.where(AnnonceHistorique.created_at < _debut_du_jour(date_fin + timedelta(days=1)))

    requete = requete.order_by(AnnonceHistorique.created_at.desc(), AnnonceHistorique.id.desc())
    pagination = db.paginate(requete, page=page, per_page=per_page, error_out=False)

    return {
        "items": [entree.to_dict() for entree in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    }


def historique_annonce(annonce_id: int, owner_id: int) -> list[dict[str, Any]]:
    """Renvoie tout l'historique d'une annonce, de la plus récente à la plus ancienne action.

    Fonctionne aussi pour une annonce supprimée (son historique est conservé).

    Args:
        annonce_id: Identifiant de l'annonce.
        owner_id: Propriétaire connecté (historique de ses annonces uniquement).

    Returns:
        list[dict[str, Any]]: Entrées sérialisées (liste vide si aucune).
    """
    requete = (
        select(AnnonceHistorique)
        .where(AnnonceHistorique.annonce_id == annonce_id, AnnonceHistorique.owner_id == owner_id)
        .order_by(AnnonceHistorique.created_at.desc(), AnnonceHistorique.id.desc())
    )
    return [entree.to_dict() for entree in db.session.scalars(requete)]


def dernieres_actions(owner_id: int, nombre: int = 5) -> list[dict[str, Any]]:
    """Renvoie les dernières actions sur les annonces d'un propriétaire.

    Args:
        owner_id: Propriétaire connecté.
        nombre: Nombre d'entrées voulues.

    Returns:
        list[dict[str, Any]]: Entrées sérialisées, de la plus récente à la plus ancienne.
    """
    requete = (
        select(AnnonceHistorique)
        .where(AnnonceHistorique.owner_id == owner_id)
        .order_by(AnnonceHistorique.created_at.desc(), AnnonceHistorique.id.desc())
        .limit(nombre)
    )
    return [entree.to_dict() for entree in db.session.scalars(requete)]
