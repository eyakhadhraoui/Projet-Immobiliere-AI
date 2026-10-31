"""Modèles du module « Gestion des visites »."""

from __future__ import annotations

import enum
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc

if TYPE_CHECKING:
    from app.models.annonce import Annonce
    from app.models.utilisateur import Utilisateur


class StatutVisite(enum.StrEnum):
    """Statuts du cycle de vie d'une visite."""

    EN_ATTENTE = "en_attente"
    CONFIRMEE = "confirmee"
    REFUSEE = "refusee"
    ANNULEE = "annulee"
    REPORTEE = "reportee"
    EFFECTUEE = "effectuee"
    ABSENT = "absent"


class TypeVisite(enum.StrEnum):
    """Format de la visite."""

    SUR_PLACE = "sur_place"
    VIRTUELLE = "virtuelle"


class Visite(db.Model):
    """Visite programmée pour une annonce immobilière."""

    __tablename__ = "visites"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False, index=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    proprietaire_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    recherche_id: Mapped[int | None] = mapped_column(
        db.Integer, db.ForeignKey("recherches_visites.id", ondelete="SET NULL"), nullable=True, index=True
    )

    date_visite: Mapped[date] = mapped_column(db.Date, nullable=False, index=True)
    heure_debut: Mapped[str] = mapped_column(db.String(10), nullable=False)
    heure_fin: Mapped[str] = mapped_column(db.String(10), nullable=False)

    statut: Mapped[StatutVisite] = mapped_column(
        db.Enum(StatutVisite, name="statut_visite", values_callable=_enum_values),
        nullable=False,
        default=StatutVisite.EN_ATTENTE,
        index=True,
    )
    type_visite: Mapped[TypeVisite] = mapped_column(
        db.Enum(TypeVisite, name="type_visite", values_callable=_enum_values),
        nullable=False,
        default=TypeVisite.SUR_PLACE,
    )
    nb_personnes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1)
    telephone_contact: Mapped[str] = mapped_column(db.String(20), nullable=False)

    message_client: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    motif_refus: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    annulee_par: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    feedback_client: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    note_visite: Mapped[int | None] = mapped_column(db.Integer, nullable=True)

    date_demande: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    date_confirmation: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    annonce = relationship("Annonce", backref=db.backref("visites", cascade="all, delete-orphan", passive_deletes=True))
    client = relationship("Utilisateur", foreign_keys=[client_id], backref="visites_demandees")
    proprietaire = relationship("Utilisateur", foreign_keys=[proprietaire_id], backref="visites_recues")

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'objet Visite en dictionnaire JSON."""
        return {
            "id": self.id,
            "reference": self.reference,
            "annonce_id": self.annonce_id,
            "recherche_id": self.recherche_id,
            "titre_annonce": self.annonce.titre if self.annonce else "Annonce",
            "ville_annonce": self.annonce.ville if self.annonce else "",
            "client_id": self.client_id,
            "client_nom": f"{self.client.prenom} {self.client.nom}".strip() if self.client else "Client",
            "client_email": self.client.email if self.client else "",
            "proprietaire_id": self.proprietaire_id,
            "proprietaire_nom": f"{self.proprietaire.prenom} {self.proprietaire.nom}".strip() if self.proprietaire else "Propriétaire",
            "date_visite": self.date_visite.isoformat() if self.date_visite else None,
            "heure_debut": self.heure_debut,
            "heure_fin": self.heure_fin,
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "type_visite": self.type_visite.value if hasattr(self.type_visite, "value") else str(self.type_visite),
            "nb_personnes": self.nb_personnes,
            "telephone_contact": self.telephone_contact,
            "message_client": self.message_client,
            "motif_refus": self.motif_refus,
            "annulee_par": self.annulee_par,
            "feedback_client": self.feedback_client,
            "note_visite": self.note_visite,
            "date_demande": en_iso_utc(self.date_demande),
            "date_confirmation": en_iso_utc(self.date_confirmation),
            "rappels": [
                {"type": "24h", "date_envoi": en_iso_utc(self.rappel_24h_le)},
                {"type": "2h", "date_envoi": en_iso_utc(self.rappel_2h_le)},
            ],
        }

    @property
    def debut_datetime(self) -> datetime:
        """Retourne le début de la visite en UTC."""
        debut = datetime.combine(self.date_visite, time.fromisoformat(self.heure_debut))
        return debut.replace(tzinfo=timezone.utc)

    @property
    def rappel_24h_le(self) -> datetime:
        """Date théorique d'envoi du rappel à 24 heures."""
        return self.debut_datetime - timedelta(hours=24)

    @property
    def rappel_2h_le(self) -> datetime:
        """Date théorique d'envoi du rappel à 2 heures."""
        return self.debut_datetime - timedelta(hours=2)


class DisponibiliteVisite(db.Model):
    """Créneaux hebdomadaires disponibles pour les visites."""

    __tablename__ = "disponibilites_visite"

    id: Mapped[int] = mapped_column(primary_key=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True)
    jour_semaine: Mapped[int] = mapped_column(db.SmallInteger, nullable=False)  # 1 (Lundi) à 7 (Dimanche)
    heure_debut: Mapped[str] = mapped_column(db.String(10), nullable=False)
    heure_fin: Mapped[str] = mapped_column(db.String(10), nullable=False)
    actif: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'objet DisponibiliteVisite en dictionnaire."""
        return {
            "id": self.id,
            "annonce_id": self.annonce_id,
            "jour_semaine": self.jour_semaine,
            "heure_debut": self.heure_debut,
            "heure_fin": self.heure_fin,
            "actif": self.actif,
        }


class RechercheVisite(db.Model):
    """Recherche de visite et candidats admissibles, conservés pour l'évaluation future."""

    __tablename__ = "recherches_visites"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int | None] = mapped_column(
        db.Integer, db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    criteres: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False)
    candidats_annonce_ids: Mapped[list[int]] = mapped_column(db.JSON, nullable=False)
    methode_classement: Mapped[str] = mapped_column(db.String(30), nullable=False)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise les métadonnées non sensibles de la recherche."""
        return {
            "id": self.id,
            "criteres": self.criteres,
            "candidats_annonce_ids": self.candidats_annonce_ids,
            "methode_classement": self.methode_classement,
            "cree_le": en_iso_utc(self.cree_le),
        }


class CreneauVisiteReserve(db.Model):
    """Verrou atomique évitant que deux demandes réservent le même créneau."""

    __tablename__ = "creneaux_visites_reserves"
    __table_args__ = (
        db.UniqueConstraint("annonce_id", "date_visite", "heure_debut", name="uq_creneau_visite_annonce_date_debut"),
        db.UniqueConstraint("visite_id", name="uq_creneau_visite_visite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False)
    date_visite: Mapped[date] = mapped_column(db.Date, nullable=False)
    heure_debut: Mapped[str] = mapped_column(db.String(10), nullable=False)
    visite_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("visites.id", ondelete="CASCADE"), nullable=False)
