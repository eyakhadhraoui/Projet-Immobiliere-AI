"""Routes du compte utilisateur (préfixe ``/api/auth``) : chaque utilisateur gère son propre compte.

Les jetons sont dans des cookies httpOnly ; toute requête POST / PUT / DELETE authentifiée doit envoyer
l'en-tête ``X-CSRF-TOKEN`` avec la valeur du cookie ``csrf_access_token`` (``csrf_refresh_token`` pour
``/rafraichir``), sinon elle est refusée (403).
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, jwt_required, unset_jwt_cookies
from sqlalchemy import select

from app.schemas.utilisateur_schema import (
    ChangementMotDePasseSchema,
    ConnexionSchema,
    InscriptionSchema,
    ProfilSchema,
    SuppressionCompteSchema,
)
from app import db
from app.securite import poser_cookies_session
from app.services import utilisateur_service
from app.services import securite_connexion_service
from app.errors import IdentifiantsInvalides, TropDeTentatives
from app.models import Utilisateur

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_inscription_schema = InscriptionSchema()
_connexion_schema = ConnexionSchema()
_profil_schema = ProfilSchema()
_mot_de_passe_schema = ChangementMotDePasseSchema()
_suppression_schema = SuppressionCompteSchema()


@bp.post("/inscription")
def inscription() -> ResponseReturnValue:
    """Crée un compte (client ou propriétaire) et ouvre la session.

    Returns:
        ResponseReturnValue: 201 avec le compte et les cookies de session, 400 ou 409.
    """
    donnees = _inscription_schema.load(request.get_json())
    utilisateur = utilisateur_service.creer_compte(donnees, request.remote_addr)
    return poser_cookies_session(jsonify(utilisateur.to_dict()), utilisateur), 201


@bp.post("/connexion")
def connexion() -> ResponseReturnValue:
    """Ouvre une session.

    Returns:
        ResponseReturnValue: 200 avec le compte et les cookies, 400, 401 (identifiants incorrects,
        même message que l'email existe ou non) ou 429 (trop de tentatives).
    """
    donnees = _connexion_schema.load(request.get_json())
    try:
        utilisateur = utilisateur_service.authentifier(
            donnees["email"], donnees["mot_de_passe"], request.remote_addr
        )
    except (IdentifiantsInvalides, TropDeTentatives):
        email = utilisateur_service.normaliser_email(donnees["email"])
        compte = db.session.scalar(select(Utilisateur).where(Utilisateur.email == email))
        try:
            securite_connexion_service.enregistrer_echec(
                compte.id if compte else None, request.remote_addr, request.user_agent.string
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Impossible d'enregistrer l'échec de connexion")
        raise
    evaluation = securite_connexion_service.enregistrer_connexion(
        utilisateur, request.remote_addr, request.user_agent.string, True
    )
    if evaluation["niveau"] == "tres_eleve":
        try:
            jeton = securite_connexion_service.creer_verification(utilisateur, evaluation["evenement_id"])
        except Exception as erreur:
            current_app.logger.exception("Envoi du code de vérification impossible")
            return jsonify(error="verification_indisponible",
                          message="Connexion inhabituelle détectée, mais l’envoi du code e-mail est indisponible. Réessayez plus tard."), 503
        reponse = jsonify(verification_requise=True, jeton_verification=jeton,
                          message="Connexion inhabituelle. Saisissez le code envoyé par e-mail.")
        unset_jwt_cookies(reponse)
        return reponse, 202
    donnees_reponse = utilisateur.to_dict()
    if evaluation["niveau"] == "suspect":
        donnees_reponse["alerte_connexion"] = {
            "evenement_id": evaluation["evenement_id"],
            "message": "Cette connexion semble inhabituelle. Confirmez si vous en êtes à l’origine.",
        }
    return poser_cookies_session(jsonify(donnees_reponse), utilisateur), 200


@bp.post("/verification-connexion")
def verification_connexion() -> ResponseReturnValue:
    """Valide le code e-mail avant d'émettre les cookies JWT."""
    donnees = request.get_json()
    if not isinstance(donnees, dict) or not isinstance(donnees.get("jeton"), str) \
            or not isinstance(donnees.get("code"), str) or len(donnees["code"]) != 6 \
            or not donnees["code"].isdigit():
        return jsonify(error="validation", message="Le code de vérification doit contenir six chiffres."), 400
    utilisateur = securite_connexion_service.valider_verification(donnees["jeton"], donnees["code"])
    return poser_cookies_session(jsonify(utilisateur.to_dict()), utilisateur), 200


@bp.post("/connexions/<int:evenement_id>/retour")
@jwt_required()
def retour_connexion(evenement_id: int) -> ResponseReturnValue:
    """Permet au compte connecté de confirmer ou de contester un événement qui lui appartient."""
    donnees = request.get_json()
    if not isinstance(donnees, dict) or donnees.get("retour") not in {"confirmee", "refusee"}:
        return jsonify(error="validation", message="Le retour doit être « confirmee » ou « refusee »."), 400
    confirme = donnees["retour"] == "confirmee"
    securite_connexion_service.retour_evenement(current_user, evenement_id, confirme)
    if not confirme:
        reponse = jsonify(message="Signalement enregistré. Toutes vos sessions ont été fermées.")
        unset_jwt_cookies(reponse)
        return reponse, 200
    return jsonify(message="Connexion confirmée."), 200


@bp.get("/connexions/alerte")
@jwt_required()
def alerte_connexion() -> ResponseReturnValue:
    """Retourne l'alerte inhabituelle non traitée du compte connecté, s'il y en a une."""
    return jsonify(securite_connexion_service.alerte_recente(current_user)), 200


@bp.get("/connexions/historique")
@jwt_required()
def historique_connexions() -> ResponseReturnValue:
    """Historique privé, limité au compte connecté; les IP et empreintes ne sont jamais exposées."""
    try:
        limite = int(request.args.get("limite", "50"))
    except ValueError:
        limite = 50
    return jsonify(items=securite_connexion_service.historique_connexions(current_user, limite)), 200


@bp.post("/deconnexion")
def deconnexion() -> ResponseReturnValue:
    """Ferme la session en effaçant les cookies (fonctionne même si la session a déjà expiré).

    Returns:
        ResponseReturnValue: 200.
    """
    reponse = jsonify(message="Vous êtes déconnecté.")
    unset_jwt_cookies(reponse)
    return reponse, 200


@bp.post("/rafraichir")
@jwt_required(refresh=True)
def rafraichir() -> ResponseReturnValue:
    """Renouvelle les jetons à partir du jeton de rafraîchissement.

    Returns:
        ResponseReturnValue: 200 avec le compte et de nouveaux cookies, ou 401.
    """
    return poser_cookies_session(jsonify(current_user.to_dict()), current_user), 200


@bp.get("/moi")
@jwt_required()
def lire_compte() -> ResponseReturnValue:
    """Renvoie le compte de l'utilisateur connecté (sans hash du mot de passe, CIN masquée).

    Returns:
        ResponseReturnValue: 200 avec le compte, ou 401.
    """
    return jsonify(current_user.to_dict()), 200


@bp.put("/moi")
@jwt_required()
def modifier_compte() -> ResponseReturnValue:
    """Modifie le profil (seuls les champs envoyés ; le rôle n'est pas modifiable).

    Returns:
        ResponseReturnValue: 200 avec le compte modifié, 400, 401 ou 409.
    """
    donnees = _profil_schema.load(request.get_json(), partial=True)
    utilisateur = utilisateur_service.modifier_profil(current_user, donnees, request.remote_addr)
    return jsonify(utilisateur.to_dict()), 200


@bp.put("/moi/mot-de-passe")
@jwt_required()
def changer_mot_de_passe() -> ResponseReturnValue:
    """Change le mot de passe (ancien obligatoire) ; les autres sessions sont fermées.

    Returns:
        ResponseReturnValue: 200 avec le compte et de nouveaux cookies pour cette session, 400 ou 401.
    """
    donnees = _mot_de_passe_schema.load(request.get_json())
    utilisateur = utilisateur_service.changer_mot_de_passe(
        current_user, donnees["ancien_mot_de_passe"], donnees["nouveau_mot_de_passe"], request.remote_addr
    )
    return poser_cookies_session(jsonify(utilisateur.to_dict()), utilisateur), 200


@bp.post("/moi/photo")
@jwt_required()
def ajouter_photo() -> ResponseReturnValue:
    """Remplace la photo de profil (multipart/form-data, champ ``photo``).

    Returns:
        ResponseReturnValue: 200 avec le compte, 400, 401 ou 413.
    """
    utilisateur = utilisateur_service.definir_photo(current_user, request.files.get("photo"), request.remote_addr)
    return jsonify(utilisateur.to_dict()), 200


@bp.delete("/moi/photo")
@jwt_required()
def retirer_photo() -> ResponseReturnValue:
    """Retire la photo de profil.

    Returns:
        ResponseReturnValue: 200 avec le compte, ou 401.
    """
    utilisateur = utilisateur_service.supprimer_photo(current_user, request.remote_addr)
    return jsonify(utilisateur.to_dict()), 200


@bp.delete("/moi")
@jwt_required()
def supprimer_compte() -> ResponseReturnValue:
    """Supprime le compte (mot de passe obligatoire), sa photo et les annonces du propriétaire.

    Returns:
        ResponseReturnValue: 204 avec les cookies effacés, 400 ou 401.
    """
    donnees = _suppression_schema.load(request.get_json())
    utilisateur_service.supprimer_compte(current_user, donnees["mot_de_passe"], request.remote_addr)
    reponse = jsonify()
    unset_jwt_cookies(reponse)
    return reponse, 204
