"""Dernier résultat de contrôle de fiabilité d'une annonce."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.models.annonce import _utcnow, en_iso_utc


class AnnonceControleFiabilite(db.Model):
    """Résultat interne du dernier contrôle d'une annonce."""

    __tablename__ = "controle_fiabilite"
    __table_args__ = (db.UniqueConstraint("annonce_id", name="uq_controle_fiabilite_annonce"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    annonce_id: Mapped[int] = mapped_column(
        db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    niveau: Mapped[str] = mapped_column(db.String(32), nullable=False)
    score: Mapped[int] = mapped_column(db.Integer, nullable=False)
    raisons: Mapped[list[dict[str, Any]]] = mapped_column(db.JSON, nullable=False, default=list)
    doublons: Mapped[list[dict[str, Any]]] = mapped_column(db.JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(db.String(32), nullable=False)
    modele_texte: Mapped[str] = mapped_column(db.String(64), nullable=False)
    version: Mapped[str] = mapped_column(db.String(32), nullable=False)
    calcule_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    def proprietaire_dict(self) -> dict[str, Any]:
        """Expose uniquement les informations autorisées au propriétaire."""
        return {
            "niveau": self.niveau,
            "score": self.score,
            "raisons": self.raisons or [],
            "decision": self.decision,
            "modele_texte": self.modele_texte,
            "version": self.version,
            "calcule_le": en_iso_utc(self.calcule_le),
        }
