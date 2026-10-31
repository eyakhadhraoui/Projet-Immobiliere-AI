"""Routes de l'historique des annonces et des statistiques (préfixe ``/api``).

Réservées aux propriétaires connectés (USER-002) : chacun ne voit que ses annonces, y compris supprimées.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user
from flask.typing import ResponseReturnValue
from sqlalchemy import exists, select
from werkzeug.exceptions import NotFound

from app import db
from app.models import Annonce
from app.schemas.historique_schema import HistoriqueFiltreSchema
from app.securite import proprietaire_requis
from app.services import historique_service, statistiques_service

bp = Blueprint("historique", __name__, url_prefix="/api")

_filtre_schema = HistoriqueFiltreSchema()


@bp.get("/annonces/<int:annonce_id>/historique")
@proprietaire_requis
def historique_annonce(annonce_id: int) -> ResponseReturnValue:
    """Renvoie l'historique complet d'une annonce du propriétaire connecté, même supprimée.

    Args:
        annonce_id: Identifiant de l'annonce.

    Returns:
        ResponseReturnValue: 200 avec ``{"items": [...]}`` ; 401 / 403 ; 404 si l'annonce n'appartient
        pas au compte connecté (ou n'existe pas) et n'a pas d'historique à son nom.
    """
    items = historique_service.historique_annonce(annonce_id, owner_id=current_user.id)
    possedee = exists().where(Annonce.id == annonce_id, Annonce.owner_id == current_user.id)
    if not items and not db.session.scalar(select(possedee)):
        raise NotFound(f"Annonce {annonce_id} introuvable")
    return jsonify(items=items), 200


@bp.get("/historique")
@proprietaire_requis
def lister_historique() -> ResponseReturnValue:
    """Liste l'historique des annonces du propriétaire connecté, filtré et paginé.

    Returns:
        ResponseReturnValue: 200 avec ``items``, ``page``, ``per_page``, ``total`` ; 400, 401 ou 403.
    """
    params = _filtre_schema.load(request.args)
    page = params.pop("page")
    per_page = params.pop("per_page")
    return jsonify(historique_service.lister_historique(params, current_user.id, page, per_page)), 200


@bp.get("/historique/<int:entree_id>")
@proprietaire_requis
def detail_historique(entree_id: int) -> ResponseReturnValue:
    """Renvoie le détail complet d'une entrée d'historique."""
    entree = db.session.get(AnnonceHistorique, entree_id)
    if not entree or entree.owner_id != current_user.id:
        raise NotFound(f"Entrée d'historique {entree_id} introuvable.")
    return jsonify(entree.to_dict()), 200


@bp.post("/historique")
@proprietaire_requis
def creer_historique() -> ResponseReturnValue:
    """Ajoute manuellement une entrée d'historique ou note d'audit."""
    donnees = request.get_json() or {}
    annonce_id = donnees.get("annonce_id", 0)
    titre_annonce = donnees.get("titre_annonce", "Audit général")
    action_nom = donnees.get("action", "modification")
    details = donnees.get("details", {})
    if isinstance(details, str):
        details = {"note": details}

    entree = AnnonceHistorique(
        annonce_id=annonce_id,
        titre_annonce=titre_annonce,
        action=ActionHistorique(action_nom),
        details=details,
        owner_id=current_user.id,
    )
    db.session.add(entree)
    db.session.commit()
    return jsonify(entree.to_dict()), 201


@bp.delete("/historique/<int:entree_id>")
@proprietaire_requis
def supprimer_historique(entree_id: int) -> ResponseReturnValue:
    """Supprime une entrée d'historique après confirmation."""
    entree = db.session.get(AnnonceHistorique, entree_id)
    if not entree or entree.owner_id != current_user.id:
        raise NotFound(f"Entrée d'historique {entree_id} introuvable.")
    db.session.delete(entree)
    db.session.commit()
    return jsonify({"message": f"Entrée d'historique #{entree_id} supprimée avec succès."}), 200


@bp.get("/statistiques")
@proprietaire_requis
def statistiques() -> ResponseReturnValue:
    """Renvoie les statistiques du tableau de bord (annonces du propriétaire connecté).

    Returns:
        ResponseReturnValue: 200 avec total, par_statut, par_type,
        prix_moyen, visites_en_attente, loyers_en_retard, etc.
    """
    return jsonify(statistiques_service.calculer_statistiques(current_user.id)), 200

