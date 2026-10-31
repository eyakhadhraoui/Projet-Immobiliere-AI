"""Gestionnaires d'erreurs globaux : toutes les erreurs sont renvoyées en JSON."""

from __future__ import annotations

from typing import NoReturn

from flask import Flask, Request, jsonify
from flask.typing import ResponseReturnValue
from marshmallow import ValidationError
from werkzeug.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    HTTPException,
    RequestEntityTooLarge,
    ServiceUnavailable,
    TooManyRequests,
    Unauthorized,
    UnsupportedMediaType,
)

from app import db


class Conflit(Conflict):
    """409 : la ressource existe déjà (ex. email déjà utilisé)."""

    code_erreur = "conflit"


class Interdit(Forbidden):
    """403 : connecté, mais sans le droit d'effectuer cette action."""

    code_erreur = "forbidden"


class NonAuthentifie(Unauthorized):
    """401 : aucune session valide."""

    code_erreur = "non_authentifie"
    description = "Veuillez vous connecter."


class IdentifiantsInvalides(Unauthorized):
    """401 : email ou mot de passe incorrect (même message que l'email existe ou non)."""

    code_erreur = "identifiants_invalides"
    description = "Email ou mot de passe incorrect."


class TropDeTentatives(TooManyRequests):
    """429 : connexion temporairement bloquée après trop d'échecs."""

    code_erreur = "trop_de_tentatives"


class ModeleNonEntraine(ServiceUnavailable):
    """503 : le modèle d'IA n'est pas encore entraîné (ou ne peut pas être chargé)."""

    code_erreur = "modele_indisponible"


class RequeteFr(Request):
    """Requête Flask dont les erreurs de lecture du corps JSON sont en français."""

    def on_json_loading_failed(self, e: ValueError | None) -> NoReturn:
        """Lève une erreur HTTP explicite quand le corps JSON est illisible.

        Args:
            e: Erreur de décodage, ou ``None`` si le Content-Type n'est pas JSON.

        Raises:
            UnsupportedMediaType: Si le Content-Type n'est pas ``application/json`` (415).
            BadRequest: Si le corps n'est pas un JSON valide (400).
        """
        if e is None:
            raise UnsupportedMediaType("Le Content-Type de la requête doit être « application/json ».")
        raise BadRequest("Le corps de la requête n'est pas un JSON valide.") from e


def register_error_handlers(app: Flask) -> None:
    """Enregistre les gestionnaires d'erreurs JSON sur l'application.

    Formats renvoyés :
        - 400 validation : ``{"error": "validation", "details": {...}}``
        - erreurs HTTP (400, 404, 405, 415…) : ``{"error": "not_found", "message": "..."}``
        - 413 (requête plus grosse que ``MAX_CONTENT_LENGTH``) : message en français
        - 500 : ``{"error": "internal_error", "message": "..."}``

    Args:
        app: Application Flask.
    """

    @app.errorhandler(ValidationError)
    def erreur_validation(erreur: ValidationError) -> ResponseReturnValue:
        return jsonify(error="validation", details=erreur.messages), 400

    @app.errorhandler(RequestEntityTooLarge)
    def erreur_trop_volumineux(erreur: RequestEntityTooLarge) -> ResponseReturnValue:
        limite_mo = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
        message = f"La requête dépasse la taille maximale autorisée ({limite_mo:g} Mo)."
        return jsonify(error="request_entity_too_large", message=message), 413

    @app.errorhandler(HTTPException)
    def erreur_http(erreur: HTTPException) -> ResponseReturnValue:
        code = getattr(erreur, "code_erreur", None) or erreur.name.lower().replace(" ", "_")
        return jsonify(error=code, message=erreur.description), erreur.code

    @app.errorhandler(Exception)
    def erreur_interne(erreur: Exception) -> ResponseReturnValue:
        db.session.rollback()
        app.logger.exception("Erreur non gérée : %s", erreur)
        return jsonify(error="internal_error", message="Erreur interne du serveur"), 500
