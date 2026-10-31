"""Modèles du module « Gestion des locations » (baux, loyers mensuels et états des lieux)."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc

if TYPE_CHECKING:
    from app.models.annonce import Annonce
    from app.models.utilisateur import Utilisateur


class TypeLocation(enum.StrEnum):
    """Catégorie de bail locatif."""

    LONGUE_DUREE = "longue_duree"
    SAISONNIERE = "saisonniere"
    MEUBLEE = "meublee"
    COMMERCIALE = "commerciale"


class PeriodiciteLocation(enum.StrEnum):
    """Périodicité d'exigibilité des loyers."""

    MENSUEL = "mensuel"
    TRIMESTRIEL = "trimestriel"
    ANNUEL = "annuel"


class StatutLocation(enum.StrEnum):
    """Statuts d'un contrat de location."""

    BROUILLON = "brouillon"
    EN_ATTENTE_SIGNATURE = "en_attente_signature"
    ACTIVE = "active"
    EN_PREAVIS = "en_preavis"
    TERMINEE = "terminee"
    RESILIEE = "resiliee"
    IMPAYEE = "impayee"


class StatutLoyer(enum.StrEnum):
    """Statut de règlement d'une échéance de loyer."""

    A_PAYER = "a_payer"
    PAYE = "paye"
    PARTIEL = "partiel"
    EN_RETARD = "en_retard"


class LocationImmo(db.Model):
    """Contrat de bail immobilier."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False, index=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True)
    proprietaire_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    locataire_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)

    type_location: Mapped[TypeLocation] = mapped_column(
        db.Enum(TypeLocation, name="type_location_enum", values_callable=_enum_values),
        nullable=False,
        default=TypeLocation.LONGUE_DUREE,
    )
    date_debut: Mapped[date] = mapped_column(db.Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(db.Date, nullable=False)
    duree_mois: Mapped[int] = mapped_column(db.Integer, nullable=False, default=12)

    loyer_mensuel: Mapped[Decimal] = mapped_column(db.Numeric(10, 3), nullable=False)
    charges: Mapped[Decimal | None] = mapped_column(db.Numeric(10, 3), nullable=True, default=Decimal("0.000"))
    caution: Mapped[Decimal] = mapped_column(db.Numeric(10, 3), nullable=False, default=Decimal("0.000"))
    jour_paiement: Mapped[int] = mapped_column(db.SmallInteger, nullable=False, default=5)
    periodicite: Mapped[PeriodiciteLocation] = mapped_column(
        db.Enum(PeriodiciteLocation, name="periodicite_location_enum", values_callable=_enum_values),
        nullable=False,
        default=PeriodiciteLocation.MENSUEL,
    )
    revalorisation_annuelle: Mapped[Decimal | None] = mapped_column(db.Numeric(5, 2), nullable=True)
    renouvellement_auto: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    preavis_jours: Mapped[int] = mapped_column(db.Integer, nullable=False, default=90)

    statut: Mapped[StatutLocation] = mapped_column(
        db.Enum(StatutLocation, name="statut_location_enum", values_callable=_enum_values),
        nullable=False,
        default=StatutLocation.ACTIVE,
        index=True,
    )

    contrat_pdf: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    etat_des_lieux_entree: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    etat_des_lieux_sortie: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    date_resiliation: Mapped[date | None] = mapped_column(db.Date, nullable=True)
    motif_resiliation: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    date_creation: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    annonce = relationship("Annonce", backref=db.backref("locations", cascade="all, delete-orphan", passive_deletes=True))
    proprietaire = relationship("Utilisateur", foreign_keys=[proprietaire_id], backref="locations_bailleurs")
    locataire = relationship("Utilisateur", foreign_keys=[locataire_id], backref="locations_locataires")
    loyers = relationship("Loyer", back_populates="location", cascade="all, delete-orphan")
    etats_des_lieux = relationship("EtatDesLieux", back_populates="location", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'objet LocationImmo en dictionnaire JSON."""
        return {
            "id": self.id,
            "reference": self.reference,
            "annonce_id": self.annonce_id,
            "titre_annonce": self.annonce.titre if self.annonce else "Bien",
            "ville_annonce": self.annonce.ville if self.annonce else "",
            "proprietaire_id": self.proprietaire_id,
            "proprietaire_nom": f"{self.proprietaire.prenom} {self.proprietaire.nom}".strip() if self.proprietaire else "Bailleur",
            "locataire_id": self.locataire_id,
            "locataire_nom": f"{self.locataire.prenom} {self.locataire.nom}".strip() if self.locataire else "Locataire",
            "transaction_id": self.transaction_id,
            "type_location": self.type_location.value if hasattr(self.type_location, "value") else str(self.type_location),
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "duree_mois": self.duree_mois,
            "loyer_mensuel": float(self.loyer_mensuel) if self.loyer_mensuel is not None else 0.0,
            "charges": float(self.charges) if self.charges is not None else 0.0,
            "caution": float(self.caution) if self.caution is not None else 0.0,
            "jour_paiement": self.jour_paiement,
            "periodicite": self.periodicite.value if hasattr(self.periodicite, "value") else str(self.periodicite),
            "revalorisation_annuelle": float(self.revalorisation_annuelle) if self.revalorisation_annuelle is not None else None,
            "renouvellement_auto": self.renouvellement_auto,
            "preavis_jours": self.preavis_jours,
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "contrat_pdf": self.contrat_pdf,
            "etat_des_lieux_entree": self.etat_des_lieux_entree,
            "etat_des_lieux_sortie": self.etat_des_lieux_sortie,
            "date_resiliation": self.date_resiliation.isoformat() if self.date_resiliation else None,
            "motif_resiliation": self.motif_resiliation,
            "date_creation": en_iso_utc(self.date_creation),
            "loyers": [l.to_dict() for l in (self.loyers or [])],
            "etats_des_lieux": [e.to_dict() for e in (self.etats_des_lieux or [])],
        }


class Loyer(db.Model):
    """Échéance de loyer mensuel liée à un contrat de location."""

    __tablename__ = "loyers"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    periode: Mapped[date] = mapped_column(db.Date, nullable=False, index=True)
    montant_du: Mapped[Decimal] = mapped_column(db.Numeric(10, 3), nullable=False)
    montant_paye: Mapped[Decimal] = mapped_column(db.Numeric(10, 3), nullable=False, default=Decimal("0.000"))
    date_echeance: Mapped[date] = mapped_column(db.Date, nullable=False, index=True)
    date_paiement: Mapped[date | None] = mapped_column(db.Date, nullable=True)

    statut: Mapped[StatutLoyer] = mapped_column(
        db.Enum(StatutLoyer, name="statut_loyer_enum", values_callable=_enum_values),
        nullable=False,
        default=StatutLoyer.A_PAYER,
        index=True,
    )
    penalite_retard: Mapped[Decimal | None] = mapped_column(db.Numeric(10, 3), nullable=True)
    quittance_pdf: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    location = relationship("LocationImmo", back_populates="loyers")

    def to_dict(self) -> dict[str, Any]:
        """Convertit le loyer en dictionnaire."""
        return {
            "id": self.id,
            "location_id": self.location_id,
            "periode": self.periode.isoformat() if self.periode else None,
            "montant_du": float(self.montant_du) if self.montant_du is not None else 0.0,
            "montant_paye": float(self.montant_paye) if self.montant_paye is not None else 0.0,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "date_paiement": self.date_paiement.isoformat() if self.date_paiement else None,
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "penalite_retard": float(self.penalite_retard) if self.penalite_retard is not None else None,
            "quittance_pdf": self.quittance_pdf,
        }


class EtatDesLieux(db.Model):
    """Constat d'état des lieux d'entrée ou de sortie."""

    __tablename__ = "etats_des_lieux"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(db.String(20), nullable=False, default="entree")
    date_edl: Mapped[date] = mapped_column(db.Date, nullable=False)
    observations: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    photos: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    signe_proprietaire: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    signe_locataire: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)

    location = relationship("LocationImmo", back_populates="etats_des_lieux")

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'état des lieux en dictionnaire."""
        return {
            "id": self.id,
            "location_id": self.location_id,
            "type": self.type,
            "date_edl": self.date_edl.isoformat() if self.date_edl else None,
            "observations": self.observations,
            "photos": self.photos or [],
            "signe_proprietaire": self.signe_proprietaire,
            "signe_locataire": self.signe_locataire,
        }
