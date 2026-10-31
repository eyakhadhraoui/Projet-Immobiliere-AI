"""Schéma Marshmallow de ``POST /api/ia/estimation-prix``."""

from __future__ import annotations

from marshmallow import fields, validate

from app.models import Transaction, TypeBien
from app.schemas.annonce_schema import MESSAGES, MESSAGES_ENUM, STRICTEMENT_POSITIF, SchemaFr


class EstimationPrixSchema(SchemaFr):
    """Caractéristiques du bien à estimer (mêmes noms et règles que les champs de l'annonce).

    Les équipements inconnus du modèle sont acceptés mais sans effet sur l'estimation.
    """

    type_bien = fields.Enum(TypeBien, by_value=True, required=True, error_messages=MESSAGES_ENUM)
    transaction = fields.Enum(Transaction, by_value=True, required=True, error_messages=MESSAGES_ENUM)
    ville = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100, error="Doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
    )
    surface = fields.Float(
        required=True,
        allow_nan=False,
        validate=[STRICTEMENT_POSITIF, validate.Range(max=10000, error="Doit être inférieur ou égal à {max}.")],
        error_messages=MESSAGES,
    )
    nb_pieces = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=0, max=50, error="Doit être compris entre {min} et {max}."),
        error_messages=MESSAGES,
    )
    # Facultatif et propre à l'estimation (IA-ANNONCE-PPT-001) : l'annonce elle-même n'a pas ce champ.
    nb_sdb = fields.Integer(
        load_default=None,
        allow_none=True,
        strict=True,
        validate=validate.Range(min=0, max=20, error="Doit être compris entre {min} et {max}."),
        error_messages=MESSAGES,
    )
    meuble = fields.Boolean(load_default=False, error_messages=MESSAGES)
    caracteristiques = fields.List(
        fields.String(validate=validate.Length(min=1, max=50)), load_default=list, error_messages=MESSAGES
    )
