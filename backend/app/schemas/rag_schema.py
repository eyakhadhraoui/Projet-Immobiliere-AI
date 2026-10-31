"""Schéma Marshmallow pour le chatbot RAG documentaire (``/api/rag``)."""

from __future__ import annotations

from marshmallow import fields, validate

from app.schemas.annonce_schema import MESSAGES, SchemaFr


class RagChatSchema(SchemaFr):
    """Validation de la requête envoyée au chatbot RAG."""

    message = fields.String(
        required=True,
        validate=validate.Length(min=1, max=2000, error="Le message doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
    )
    transaction = fields.String(
        load_default="general",
        validate=validate.OneOf(
            ["location", "vente", "general"],
            error="La transaction doit être 'location', 'vente' ou 'general'.",
        ),
        error_messages=MESSAGES,
    )
    elements_coches = fields.List(
        fields.String(validate=validate.Length(min=1, max=100)),
        load_default=list,
        error_messages=MESSAGES,
    )
    langue = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["fr", "ar", "auto"], error="La langue doit être 'fr', 'ar' ou 'auto'."),
        error_messages=MESSAGES,
    )
