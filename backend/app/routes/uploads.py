"""Service des fichiers images uploadés (``GET /uploads/<filename>``)."""

from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory
from flask.typing import ResponseReturnValue

bp = Blueprint("uploads", __name__)


@bp.get("/uploads/<filename>")
def servir_fichier(filename: str) -> ResponseReturnValue:
    """Renvoie une image du dossier ``UPLOAD_FOLDER``.

    ``send_from_directory`` refuse tout chemin qui sortirait du dossier (404).

    Args:
        filename: Nom du fichier (UUID + extension).

    Returns:
        ResponseReturnValue: Le fichier, ou 404 en JSON.
    """
    reponse = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse
