"""Demandes d'intervention, fil d'historique et notifications du module maintenance."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc


class CategorieMaintenance(enum.StrEnum):
    PLOMBERIE = "plomberie"
    ELECTRICITE = "electricite"
    CLIMATISATION = "climatisation"
    SERRURERIE = "serrurerie"
    ELECTROMENAGER = "electromenager"
    AUTRE = "autre"


class PrioriteMaintenance(enum.StrEnum):
    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"
    URGENTE = "urgente"


class StatutMaintenance(enum.StrEnum):
    SIGNALEE = "signalee"
    ACCEPTEE = "acceptee"
    ASSIGNEE = "assignee"
    PLANIFIEE = "planifiee"
    CLOTUREE = "cloturee"
    REFUSEE = "refusee"


class DemandeMaintenance(db.Model):
    __tablename__ = "demandes_maintenance"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(db.String(24), unique=True, nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    locataire_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    proprietaire_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    categorie: Mapped[CategorieMaintenance] = mapped_column(db.Enum(CategorieMaintenance, name="categorie_maintenance", values_callable=_enum_values), nullable=False)
    piece: Mapped[str | None] = mapped_column(db.String(32), nullable=True)
    titre: Mapped[str] = mapped_column(db.String(160), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    photos: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    priorite: Mapped[PrioriteMaintenance] = mapped_column(db.Enum(PrioriteMaintenance, name="priorite_maintenance", values_callable=_enum_values), nullable=False, default=PrioriteMaintenance.NORMALE, index=True)
    statut: Mapped[StatutMaintenance] = mapped_column(db.Enum(StatutMaintenance, name="statut_maintenance", values_callable=_enum_values), nullable=False, default=StatutMaintenance.SIGNALEE, index=True)
    technicien_nom: Mapped[str | None] = mapped_column(db.String(160), nullable=True)
    technicien_telephone: Mapped[str | None] = mapped_column(db.String(30), nullable=True)
    date_intervention: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    cout_estime: Mapped[float | None] = mapped_column(db.Numeric(12, 3), nullable=True)
    cout_reel: Mapped[float | None] = mapped_column(db.Numeric(12, 3), nullable=True)
    note_cloture: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    date_creation: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    date_maj: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    location = relationship("LocationImmo")
    locataire = relationship("Utilisateur", foreign_keys=[locataire_id])
    proprietaire = relationship("Utilisateur", foreign_keys=[proprietaire_id])
    evenements = relationship("EvenementMaintenance", cascade="all, delete-orphan", order_by="EvenementMaintenance.date_creation")

    def to_dict(self) -> dict[str, Any]:
        loc = self.location
        return {
            "id": self.id, "reference": self.reference, "location_id": self.location_id,
            "titre": self.titre, "description": self.description, "categorie": self.categorie.value,
            "piece": self.piece,
            "priorite": self.priorite.value, "statut": self.statut.value, "photos": self.photos or [],
            "technicien_nom": self.technicien_nom, "technicien_telephone": self.technicien_telephone,
            "date_intervention": en_iso_utc(self.date_intervention),
            "cout_estime": float(self.cout_estime) if self.cout_estime is not None else None,
            "cout_reel": float(self.cout_reel) if self.cout_reel is not None else None,
            "note_cloture": self.note_cloture,
            "date_creation": en_iso_utc(self.date_creation), "date_maj": en_iso_utc(self.date_maj),
            "annonce_titre": loc.annonce.titre if loc and loc.annonce else "Bien immobilier",
            "annonce_ville": loc.annonce.ville if loc and loc.annonce else "",
            "loyer_mensuel": float(loc.loyer_mensuel) if loc else 0,
            "locataire_id": self.locataire_id, "locataire_nom": f"{self.locataire.prenom} {self.locataire.nom}".strip() if self.locataire else "Locataire",
            "locataire_telephone": self.locataire.telephone if self.locataire else None,
            "proprietaire_id": self.proprietaire_id,
            "evenements": [item.to_dict() for item in self.evenements],
        }


class EvenementMaintenance(db.Model):
    __tablename__ = "evenements_maintenance"
    id: Mapped[int] = mapped_column(primary_key=True)
    demande_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("demandes_maintenance.id", ondelete="CASCADE"), nullable=False, index=True)
    auteur_id: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(db.String(40), nullable=False)
    detail: Mapped[str] = mapped_column(db.String(500), nullable=False)
    date_creation: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    auteur = relationship("Utilisateur")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "action": self.action, "detail": self.detail,
                "auteur_nom": f"{self.auteur.prenom} {self.auteur.nom}".strip() if self.auteur else "Système",
                "date_creation": en_iso_utc(self.date_creation)}


class NotificationMaintenance(db.Model):
    __tablename__ = "notifications_maintenance"
    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    demande_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("demandes_maintenance.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(db.String(300), nullable=False)
    lue: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False, index=True)
    date_creation: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "demande_id": self.demande_id, "message": self.message,
                "lue": self.lue, "date_creation": en_iso_utc(self.date_creation)}
