"""Configuration de flask-jwt-extended : jetons en cookies, réponses d'erreur en JSON français."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from flask import Flask, Response, jsonify
from flask.typing import ResponseReturnValue
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    current_user,
    get_current_user,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    verify_jwt_in_request,
)
from flask_jwt_extended.exceptions import CSRFError, JWTExtendedException
from jwt.exceptions import PyJWTError

from app import db
from app.errors import Interdit
from app.models import RoleUtilisateur, Utilisateur

jwt = JWTManager()

P = ParamSpec("P")
R = TypeVar("R")

MESSAGE_RESERVE_PROPRIETAIRES = "Espace réservé aux propriétaires."

MESSAGE_NON_AUTHENTIFIE = "Veuillez vous connecter."


def _non_authentifie(message: str = MESSAGE_NON_AUTHENTIFIE) -> ResponseReturnValue:
    """Réponse 401 commune à toutes les erreurs de jeton.

    Args:
        message: Message affiché à l'utilisateur.

    Returns:
        ResponseReturnValue: ``{"error": "non_authentifie", "message": ...}`` avec le code 401.
    """
    return jsonify(error="non_authentifie", message=message), 401


def init_securite(app: Flask) -> None:
    """Initialise JWT sur l'application et enregistre ses gestionnaires.

    Args:
        app: Application Flask.

    Raises:
        RuntimeError: Si ``JWT_SECRET_KEY`` est absente : sans elle, flask-jwt-extended utiliserait
            ``SECRET_KEY`` à la place sans prévenir.
    """
    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY manquante : ajoutez-la dans backend/.env (voir .env.example).")
    jwt.init_app(app)

    @jwt.user_identity_loader
    def identite(utilisateur: Utilisateur) -> str:
        return str(utilisateur.id)

    @jwt.additional_claims_loader
    def revendications(utilisateur: Utilisateur) -> dict[str, Any]:
        return {"ver": utilisateur.jeton_version}

    @jwt.user_lookup_loader
    def charger_utilisateur(_entete: dict[str, Any], contenu: dict[str, Any]) -> Utilisateur | None:
        # Compte supprimé, ou jeton émis avant un changement de mot de passe → session refusée.
        sujet = str(contenu.get("sub", ""))
        utilisateur = db.session.get(Utilisateur, int(sujet)) if sujet.isdigit() else None
        if utilisateur is None or utilisateur.jeton_version != contenu.get("ver"):
            return None
        return utilisateur

    @jwt.user_lookup_error_loader
    def utilisateur_introuvable(_entete: dict[str, Any], _contenu: dict[str, Any]) -> ResponseReturnValue:
        return _non_authentifie()

    @jwt.unauthorized_loader
    def jeton_absent(_raison: str) -> ResponseReturnValue:
        return _non_authentifie()

    @jwt.invalid_token_loader
    def jeton_invalide(_raison: str) -> ResponseReturnValue:
        return _non_authentifie()

    @jwt.expired_token_loader
    def jeton_expire(_entete: dict[str, Any], _contenu: dict[str, Any]) -> ResponseReturnValue:
        return _non_authentifie("Session expirée, veuillez vous reconnecter.")

    # Remplace le gestionnaire de la bibliothèque (401) : un échec CSRF est un refus, pas une absence de session.
    @app.errorhandler(CSRFError)
    def erreur_csrf(_erreur: CSRFError) -> ResponseReturnValue:
        return jsonify(error="csrf_invalide", message="Jeton CSRF manquant ou invalide."), 403


def poser_cookies_session(reponse: Response, utilisateur: Utilisateur) -> Response:
    """Ajoute à la réponse les cookies de session (jetons d'accès et de rafraîchissement + jetons CSRF).

    Args:
        reponse: Réponse Flask.
        utilisateur: Compte connecté.

    Returns:
        Response: La même réponse, avec les cookies.
    """
    set_access_cookies(reponse, create_access_token(identity=utilisateur))
    set_refresh_cookies(reponse, create_refresh_token(identity=utilisateur))
    return reponse


def utilisateur_optionnel() -> Utilisateur | None:
    """Utilisateur connecté s'il y en a un, sinon ``None`` (routes publiques).

    Un cookie expiré, invalide ou d'un compte supprimé est traité comme une visite anonyme :
    il ne doit pas empêcher de consulter le catalogue public.

    Returns:
        Utilisateur | None: Compte connecté, ou ``None``.
    """
    try:
        verify_jwt_in_request(optional=True)
    except (JWTExtendedException, PyJWTError):
        return None
    return get_current_user()  # l'objet Utilisateur lui-même (pas le proxy)


def proprietaire_requis(fonction: Callable[P, R]) -> Callable[P, R]:
    """Décorateur : connexion obligatoire (401) et rôle propriétaire (403).

    Args:
        fonction: Vue Flask à protéger.

    Returns:
        Callable[P, R]: Vue protégée.
    """

    @wraps(fonction)
    @jwt_required()
    def vue(*args: P.args, **kwargs: P.kwargs) -> R:
        if current_user.role != RoleUtilisateur.PROPRIETAIRE:
            raise Interdit(MESSAGE_RESERVE_PROPRIETAIRES)
        return fonction(*args, **kwargs)

    return vue
