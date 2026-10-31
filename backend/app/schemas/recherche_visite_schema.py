"""Validation des critères de recherche de créneaux de visite."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.models.annonce import Transaction, TypeBien


class CreneauVisiteurSchema(Schema):
    """Plage horaire durant laquelle le visiteur peut effectuer une visite."""

    debut = fields.DateTime(required=True, format="iso")
    fin = fields.DateTime(required=True, format="iso")

    @validates_schema
    def valider_plage(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Refuse les plages vides, passées ou éloignées de la fenêtre de recherche."""
        debut, fin = data.get("debut"), data.get("fin")
        maintenant = datetime.now().astimezone().replace(tzinfo=None)
        debut = debut.astimezone().replace(tzinfo=None) if debut and debut.tzinfo else debut
        fin = fin.astimezone().replace(tzinfo=None) if fin and fin.tzinfo else fin
        if debut:
            data["debut"] = debut
        if fin:
            data["fin"] = fin
        if debut and fin and (fin <= debut or debut < maintenant or fin > maintenant + timedelta(days=14)):
            raise ValidationError("Choisissez une plage future dans les 14 prochains jours.")


class RechercheVisiteSchema(Schema):
    """Critères stricts utilisés pour trouver des annonces avec créneaux compatibles."""

    villes = fields.List(fields.String(validate=validate.Length(min=1, max=100)), load_default=list,
                         validate=validate.Length(max=10))
    transaction = fields.Enum(Transaction, by_value=True, allow_none=True, load_default=None)
    type_bien = fields.Enum(TypeBien, by_value=True, allow_none=True, load_default=None)
    budget_max = fields.Float(allow_none=True, load_default=None,
                              validate=validate.Range(min=0, min_inclusive=False))
    pieces_min = fields.Integer(allow_none=True, load_default=None,
                                validate=validate.Range(min=0))
    disponibilites = fields.List(fields.Nested(CreneauVisiteurSchema), required=True,
                                 validate=validate.Length(min=1, max=10))
    tri = fields.String(load_default="pertinence",
                        validate=validate.OneOf(("pertinence", "chronologique")))

    @validates_schema
    def valider_villes(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Nettoie et valide les villes, sans accepter de critères contradictoires."""
        villes = [ville.strip() for ville in data.get("villes", [])]
        if any(not ville for ville in villes):
            raise ValidationError("Chaque ville doit contenir un nom.", field_name="villes")
        data["villes"] = list(dict.fromkeys(villes))

