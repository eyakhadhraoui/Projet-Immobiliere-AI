"""Route de diagnostic RAG isolée, sans toucher au RAG juridique existant."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import or_, select

from app import db
from app.ia.maintenance_rag.costs import CostTable
from app.ia.maintenance_rag.diagnosis import MaintenanceRagError, diagnose
from app.ia.maintenance_rag.embeddings import EmbeddingError
from app.ia.maintenance_rag.retriever import Retriever
from app.models import LocationImmo, RoleUtilisateur, StatutLocation

bp = Blueprint("maintenance_diagnostic", __name__, url_prefix="/api/maintenance/ia")
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "ia" / "maintenance_rag" / "data"
CHROMA_PATH = BACKEND_DIR / "maintenance_rag_chroma"
COSTS_PATH = DATA_DIR / "couts.json"
CATEGORIES = {"electricite", "plomberie", "chauffage", "serrurerie", "humidite", "autre",
              "climatisation", "electromenager"}
ROOMS = {"cuisine", "salle_de_bain", "salon", "chambre", "toilettes", "autre"}
URGENCIES = {"faible", "moyenne", "elevee", "critique"}
PRIORITE_TO_URGENCY = {"basse": "faible", "normale": "moyenne", "haute": "elevee", "urgente": "critique"}

_retriever: Retriever | None = None
_cost_table: CostTable | None = None


def _get_retriever() -> Retriever | None:
    global _retriever
    if _retriever is None:
        try:
            _retriever = Retriever(CHROMA_PATH, current_app.config.get("GEMINI_API_KEY", ""))
        except Exception:
            current_app.logger.exception("Index Chroma du guide maintenance indisponible (%s)", CHROMA_PATH)
            return None
    return _retriever


def _get_cost_table() -> CostTable | None:
    global _cost_table
    if _cost_table is None:
        try:
            _cost_table = CostTable(COSTS_PATH)
        except (OSError, ValueError, KeyError):
            current_app.logger.exception("Fichier de coûts maintenance illisible (%s)", COSTS_PATH)
            return None
    return _cost_table


@bp.post("/diagnose")
@jwt_required()
def diagnostiquer_maintenance():
    if current_user.role not in {RoleUtilisateur.CLIENT, RoleUtilisateur.PROPRIETAIRE}:
        return jsonify(error="Compte non autorisé à demander un diagnostic."), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Corps JSON invalide."), 400
    location_id = payload.get("location_id")
    if not isinstance(location_id, int) or isinstance(location_id, bool):
        return jsonify(errors={"location_id": "Sélectionnez un bail actif."}), 400
    location = current_user_location(location_id)
    if location is None:
        return jsonify(message="Contrat actif introuvable pour ce compte."), 404

    categorie = payload.get("category")
    piece = payload.get("room")
    urgency = payload.get("urgency")
    title = payload.get("title")
    description = payload.get("description")
    errors = {}
    if not isinstance(categorie, str) or categorie not in CATEGORIES:
        errors["category"] = "Catégorie invalide."
    if not isinstance(piece, str) or piece not in ROOMS:
        errors["room"] = "Pièce invalide."
    if not isinstance(urgency, str) or urgency not in URGENCIES:
        urgency = PRIORITE_TO_URGENCY.get(payload.get("priority"), "")
        if urgency not in URGENCIES:
            errors["urgency"] = "Urgence invalide."
    if not isinstance(title, str) or not 5 <= len(title.strip()) <= 160:
        errors["title"] = "Le titre doit contenir entre 5 et 160 caractères."
    if not isinstance(description, str) or not 10 <= len(description.strip()) <= 5000:
        errors["description"] = "La description doit contenir entre 10 et 5 000 caractères."
    if errors:
        return jsonify(errors=errors), 400
    if not current_app.config.get("GEMINI_API_KEY"):
        return jsonify(error="Service Gemini non configuré (GEMINI_API_KEY manquante)."), 503
    retriever = _get_retriever()
    if retriever is None:
        return jsonify(error="Index du guide de maintenance indisponible. Lancez l'indexation du guide."), 503
    try:
        result = diagnose(
            retriever,
            category=categorie,
            room=piece,
            urgency=urgency,
            title=title.strip(),
            description=description.strip(),
        )
    except EmbeddingError:
        current_app.logger.exception("Échec de recherche vectorielle du guide maintenance")
        return jsonify(error="La recherche dans le guide a échoué. Réessayez plus tard."), 502
    except MaintenanceRagError as err:
        return jsonify(error=err.message), err.status
    except Exception:
        current_app.logger.exception("Erreur d'index ou de génération dans le RAG maintenance")
        return jsonify(error="Le service de diagnostic est temporairement indisponible."), 503

    costs = _get_cost_table()
    result["estimation"] = costs.estimate(result["fiche_id"]) if costs else None
    return jsonify(result), 200


def current_user_location(location_id: int):
    """Ne permet de diagnostiquer qu'un signalement sur un bail actif du compte connecté."""
    return db.session.scalar(select(LocationImmo).where(
        LocationImmo.id == location_id,
        LocationImmo.statut == StatutLocation.ACTIVE,
        or_(LocationImmo.locataire_id == current_user.id, LocationImmo.proprietaire_id == current_user.id),
    ))
