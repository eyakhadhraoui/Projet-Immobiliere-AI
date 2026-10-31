"""Schéma Marshmallow des filtres de l'historique."""

from __future__ import annotations

from typing import Any

from marshmallow import EXCLUDE, ValidationError, fields, validate, validates_schema

from app.models import ActionHistorique
from app.schemas.annonce_schema import MESSAGES, MESSAGES_ENUM, SchemaFr

MESSAGES_DATE = {**MESSAGES, "invalid": "Date invalide (format attendu : AAAA-MM-JJ)."}


class HistoriqueFiltreSchema(SchemaFr):
    """Valide les paramètres de requête de ``GET /api/historique``.

    Les paramètres inconnus sont ignorés. ``date_debut`` et ``date_fin`` sont incluses.
    """

    class Meta:
        unknown = EXCLUDE

    annonce_id = fields.Integer(
        validate=validate.Range(min=1, error="Doit être supérieur ou égal à {min}."),
        error_messages=MESSAGES,
    )
    recherche = fields.String(load_default="")
    action = fields.Enum(ActionHistorique, by_value=True, error_messages=MESSAGES_ENUM)
    date_debut = fields.Date(error_messages=MESSAGES_DATE)
    date_fin = fields.Date(error_messages=MESSAGES_DATE)
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1, error="Doit être supérieur ou égal à {min}."),
        error_messages=MESSAGES,
    )
    per_page = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, error="Doit être supérieur ou égal à {min}."),
        error_messages=MESSAGES,
    )

    @validates_schema
    def verifier_periode(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Vérifie que ``date_debut`` ne dépasse pas ``date_fin``.

        Args:
            data: Paramètres déjà désérialisés.
            **kwargs: Arguments transmis par Marshmallow (``partial``, ``many``).

        Raises:
            ValidationError: Si ``date_debut`` est postérieure à ``date_fin``.
        """
        debut, fin = data.get("date_debut"), data.get("date_fin")
        if debut is not None and fin is not None and debut > fin:
            raise ValidationError("Doit être postérieure ou égale à date_debut.", field_name="date_fin")
