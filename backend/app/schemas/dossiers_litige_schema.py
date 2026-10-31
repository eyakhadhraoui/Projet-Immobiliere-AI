"""Validation stricte des entrées de l'API des dossiers de litige."""

from marshmallow import RAISE, Schema, fields, validate


class DossierLitigeCreationSchema(Schema):
    """Champs acceptés lors de la création d'un dossier."""

    titre = fields.String(required=True, validate=validate.Length(min=1, max=160))
    description = fields.String(load_default="", validate=validate.Length(max=5000))
    langue = fields.String(load_default="fr", validate=validate.OneOf(("fr", "en")))
    location_id = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=1))
    juridiction = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=120))
    provenance = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=120))

    class Meta:
        unknown = RAISE


class QuestionLitigeSchema(Schema):
    """Question limitée et sans champs annexes implicites."""

    question = fields.String(required=True, validate=validate.Length(min=1, max=1000))

    class Meta:
        unknown = RAISE


class RapportLitigeSchema(Schema):
    """Format de rapport explicite."""

    format = fields.String(load_default="json", validate=validate.OneOf(("json", "markdown", "html", "csv")))

    class Meta:
        unknown = RAISE
