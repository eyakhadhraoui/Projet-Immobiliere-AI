"""Schémas Marshmallow de validation des annonces."""

from __future__ import annotations

from typing import Any

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

from app.models import StatutAnnonce, Transaction, TypeBien

MESSAGES = {
    "required": "Champ obligatoire.",
    "null": "Ce champ ne peut pas être nul.",
    "invalid": "Valeur invalide.",
}
MESSAGES_ENUM = {**MESSAGES, "unknown": "Doit être l'une des valeurs : {choices}."}

STRICTEMENT_POSITIF = validate.Range(min=0, min_inclusive=False, error="Doit être supérieur à 0.")
POSITIF_OU_NUL = validate.Range(min=0, error="Doit être supérieur ou égal à 0.")


class SchemaFr(Schema):
    """Schéma de base avec des messages d'erreur globaux en français."""

    error_messages = {"unknown": "Champ inconnu.", "type": "Le corps de la requête doit être un objet JSON."}


class AnnonceCreateSchema(SchemaFr):
    """Valide le corps JSON de création d'une annonce.

    Le statut n'est pas accepté ici : une annonce est toujours créée en
    ``brouillon`` et son statut se change via ``PATCH /<id>/statut``.
    ``owner_id`` n'est pas accepté non plus : c'est le propriétaire connecté (USER-002).
    """

    titre = fields.String(
        required=True,
        validate=validate.Length(min=5, max=150, error="Doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
    )
    description = fields.String(
        required=True,
        validate=validate.Length(min=1, error="Ne peut pas être vide."),
        error_messages=MESSAGES,
    )
    type_bien = fields.Enum(TypeBien, by_value=True, required=True, error_messages=MESSAGES_ENUM)
    transaction = fields.Enum(Transaction, by_value=True, required=True, error_messages=MESSAGES_ENUM)
    prix = fields.Float(required=True, allow_nan=False, validate=STRICTEMENT_POSITIF, error_messages=MESSAGES)
    surface = fields.Float(required=True, allow_nan=False, validate=STRICTEMENT_POSITIF, error_messages=MESSAGES)
    nb_pieces = fields.Integer(required=True, strict=True, validate=POSITIF_OU_NUL, error_messages=MESSAGES)
    meuble = fields.Boolean(load_default=False, error_messages=MESSAGES)
    adresse = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255, error="Doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
    )
    ville = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100, error="Doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
    )
    latitude = fields.Float(
        load_default=None,
        validate=validate.Range(min=-90, max=90, error="Doit être compris entre {min} et {max}."),
        error_messages=MESSAGES,
    )
    longitude = fields.Float(
        load_default=None,
        validate=validate.Range(min=-180, max=180, error="Doit être compris entre {min} et {max}."),
        error_messages=MESSAGES,
    )
    caracteristiques = fields.List(
        fields.String(validate=validate.Length(min=1, max=50)),
        load_default=list,
        error_messages=MESSAGES,
    )


class AnnonceUpdateSchema(AnnonceCreateSchema):
    """Valide le corps JSON de modification d'une annonce.

    Mêmes règles que la création. À charger avec ``partial=True`` : seuls les champs envoyés sont modifiés.
    """


class AnnonceStatutSchema(SchemaFr):
    """Valide le corps JSON de ``PATCH /api/annonces/<id>/statut``."""

    statut = fields.Enum(StatutAnnonce, by_value=True, required=True, error_messages=MESSAGES_ENUM)
    confirmation_fiabilite = fields.Boolean(load_default=False, error_messages=MESSAGES)


class PhotoOrdreSchema(SchemaFr):
    """Valide le corps JSON de ``PATCH /api/annonces/<id>/photos/ordre``."""

    ordre = fields.List(
        fields.Integer(strict=True, error_messages=MESSAGES),
        required=True,
        validate=validate.Length(min=1, error="La liste ne peut pas être vide."),
        error_messages=MESSAGES,
    )


class DemandeRevueSchema(SchemaFr):
    """Valide le message facultatif joint à une demande de revue humaine."""

    message = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=2000, error="Ne peut pas dépasser 2000 caractères."),
        error_messages=MESSAGES,
    )


class AnnonceFiltreSchema(SchemaFr):
    """Valide les paramètres de requête de la liste des annonces.

    Les paramètres inconnus sont ignorés.
    """

    class Meta:
        unknown = EXCLUDE

    ville = fields.String(validate=validate.Length(min=1, max=100))
    type_bien = fields.Enum(TypeBien, by_value=True, error_messages=MESSAGES_ENUM)
    transaction = fields.Enum(Transaction, by_value=True, error_messages=MESSAGES_ENUM)
    statut = fields.Enum(StatutAnnonce, by_value=True, error_messages=MESSAGES_ENUM)
    prix_min = fields.Float(allow_nan=False, validate=POSITIF_OU_NUL, error_messages=MESSAGES)
    prix_max = fields.Float(allow_nan=False, validate=POSITIF_OU_NUL, error_messages=MESSAGES)
    surface_min = fields.Float(allow_nan=False, validate=POSITIF_OU_NUL, error_messages=MESSAGES)
    meuble = fields.Boolean(error_messages=MESSAGES)
    tri = fields.String(load_default="chronologique", validate=validate.OneOf(
        ["chronologique", "pertinence"], error="Doit valoir chronologique ou pertinence."
    ))
    # true : annonces du propriétaire connecté (tous statuts) ; sinon catalogue public (publiées uniquement).
    mes_annonces = fields.Boolean(load_default=False, error_messages=MESSAGES)
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1, error="Doit être supérieur ou égal à {min}."),
        error_messages=MESSAGES,
    )
    per_page = fields.Integer(
        load_default=10,
        validate=validate.Range(min=1, error="Doit être supérieur ou égal à {min}."),
        error_messages=MESSAGES,
    )

    @validates_schema
    def verifier_fourchette_prix(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Vérifie que ``prix_min`` ne dépasse pas ``prix_max``.

        Args:
            data: Paramètres déjà désérialisés.
            **kwargs: Arguments transmis par Marshmallow (``partial``, ``many``).

        Raises:
            ValidationError: Si ``prix_min`` est supérieur à ``prix_max``.
        """
        prix_min, prix_max = data.get("prix_min"), data.get("prix_max")
        if prix_min is not None and prix_max is not None and prix_min > prix_max:
            raise ValidationError("Doit être supérieur ou égal à prix_min.", field_name="prix_max")
