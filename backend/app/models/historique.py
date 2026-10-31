"""Modèle de l'historique des actions sur les annonces."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc


class ActionHistorique(enum.StrEnum):
    """Types d'action enregistrés dans l'historique."""

    CREATION = "creation"
    MODIFICATION = "modification"
    CHANGEMENT_STATUT = "changement_statut"
    AJOUT_PHOTOS = "ajout_photos"
    SUPPRESSION_PHOTO = "suppression_photo"
    REORDONNANCEMENT_PHOTOS = "reordonnancement_photos"
    SUPPRESSION = "suppression"
    CONTROLE_FIABILITE = "controle_fiabilite"
    PUBLICATION_CONFIRMEE = "publication_confirmee"
    MISE_EN_ATTENTE = "mise_en_attente"
    ATTENTE_LEVEE = "attente_levee"
    DEMANDE_REVUE = "demande_revue"
    DECISION_MODERATION = "decision_moderation"
    NOUVELLE_TENTATIVE = "nouvelle_tentative"


class AnnonceHistorique(db.Model):
    """Action effectuée sur une annonce.

    ``annonce_id`` n'est volontairement pas une clé étrangère : l'historique d'une annonce
    supprimée doit être conservé, et ``titre_annonce`` garde le titre au moment de l'action.

    Attributes:
        details: Données propres à l'action (ex. pour une modification :
            ``{"prix": {"avant": 900, "apres": 950}}``).
    """

    __tablename__ = "annonce_historique"

    id: Mapped[int] = mapped_column(primary_key=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    titre_annonce: Mapped[str] = mapped_column(db.String(200), nullable=False)
    action: Mapped[ActionHistorique] = mapped_column(
        db.Enum(ActionHistorique, name="action_historique", values_callable=_enum_values),
        nullable=False,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    owner_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    def to_dict(self) -> dict[str, Any]:
        """Sérialise l'entrée d'historique en dictionnaire JSON-compatible.

        Returns:
            dict[str, Any]: Représentation de l'entrée.
        """
        return {
            "id": self.id,
            "annonce_id": self.annonce_id,
            "titre_annonce": self.titre_annonce,
            "action": self.action.value,
            "details": self.details or {},
            "owner_id": self.owner_id,
            "created_at": en_iso_utc(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<AnnonceHistorique {self.id} annonce={self.annonce_id} {self.action}>"
