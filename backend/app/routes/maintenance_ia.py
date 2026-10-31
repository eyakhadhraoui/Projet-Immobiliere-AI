"""Routes IA du module maintenance, isolées des routes de gestion des demandes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import or_, select
from werkzeug.exceptions import RequestEntityTooLarge

from app import db
from app.ia.maintenance_photo import IMAGE_MIMES, MAX_PHOTO_BYTES, GeminiPhotoError, analyze_photo, detect_image_type
from app.models import LocationImmo, RoleUtilisateur, StatutLocation
from app.services.photo_service import controler_image

bp = Blueprint("maintenance_ia", __name__, url_prefix="/api/maintenance/ia")


@bp.before_request
def augmenter_limite_requete_photo():
    # L'application garde sa limite globale de 5 Mo; seule cette route autorise une image plus grande.
    request.max_content_length = 10 * 1024 * 1024


@bp.errorhandler(RequestEntityTooLarge)
def photo_trop_volumineuse(_erreur):
    return jsonify(errors={"photo": "La photo doit faire moins de 10 Mo."}), 413


@bp.post("/analyze-photo")
@jwt_required()
def analyser_photo():
    if current_user.role not in {RoleUtilisateur.CLIENT, RoleUtilisateur.PROPRIETAIRE}:
        return jsonify(message="Compte non autorisé à signaler un problème."), 403

    location_id = request.form.get("location_id", type=int)
    if not location_id:
        return jsonify(errors={"location_id": "Sélectionnez un contrat de location actif."}), 400
    location = db.session.scalar(select(LocationImmo).where(
        LocationImmo.id == location_id,
        LocationImmo.statut == StatutLocation.ACTIVE,
        or_(LocationImmo.locataire_id == current_user.id, LocationImmo.proprietaire_id == current_user.id),
    ))
    if location is None:
        return jsonify(message="Contrat actif introuvable pour ce compte."), 404

    fichier = request.files.get("photo")
    if fichier is None or not fichier.filename:
        return jsonify(errors={"photo": "Sélectionnez une photo à analyser."}), 400

    contenu = fichier.stream.read(MAX_PHOTO_BYTES + 1)
    fichier.stream.seek(0)
    if len(contenu) > MAX_PHOTO_BYTES:
        return jsonify(errors={"photo": "La photo doit faire moins de 10 Mo."}), 413
    extension = detect_image_type(contenu[:16])
    if extension not in IMAGE_MIMES:
        return jsonify(errors={"photo": "Format accepté : JPEG, PNG ou WebP."}), 400
    # La signature détectée prévaut sur l'extension fournie par le navigateur.
    fichier.filename = f"photo.{extension}"
    extension_validee, erreur = controler_image(fichier)
    if erreur or extension_validee != extension:
        return jsonify(errors={"photo": erreur or "Image invalide."}), 400

    try:
        return jsonify(analyze_photo(contenu, IMAGE_MIMES[extension])), 200
    except GeminiPhotoError as erreur_gemini:
        return jsonify(error=erreur_gemini.message), erreur_gemini.status
