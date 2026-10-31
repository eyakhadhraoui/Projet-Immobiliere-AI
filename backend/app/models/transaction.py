"""Modèles du module « Gestion des transactions » (ventes, réservations et paiements)."""

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


class TypeTransaction(enum.StrEnum):
    """Nature de la transaction."""

    VENTE = "vente"
    LOCATION = "location"
    RESERVATION = "reservation"


class ModePaiement(enum.StrEnum):
    """Modes de paiement acceptés en Tunisie."""

    ESPECES = "especes"
    VIREMENT = "virement"
    CHEQUE = "cheque"
    CARTE = "carte"
    FLOUCI = "flouci"
    PAYMEE = "paymee"


class StatutTransaction(enum.StrEnum):
    """Statuts de la transaction."""

    EN_NEGOCIATION = "en_negociation"
    RESERVEE = "reservee"
    EN_COURS = "en_cours"
    PAYEE_PARTIELLEMENT = "payee_partiellement"
    FINALISEE = "finalisee"
    ANNULEE = "annulee"
    LITIGE = "litige"


class StatutPaiement(enum.StrEnum):
    """Statut d'un versement."""

    EN_ATTENTE = "en_attente"
    VALIDE = "valide"
    REFUSE = "refuse"
    REMBOURSE = "rembourse"


class TransactionImmo(db.Model):
    """Transaction immobilière (vente, location ou réservation)."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False, index=True)
    annonce_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True)

    type_transaction: Mapped[TypeTransaction] = mapped_column(
        db.Enum(TypeTransaction, name="type_transaction_enum", values_callable=_enum_values),
        nullable=False,
        default=TypeTransaction.VENTE,
    )
    vendeur_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    acheteur_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)

    montant_total: Mapped[Decimal] = mapped_column(db.Numeric(12, 3), nullable=False)
    acompte: Mapped[Decimal | None] = mapped_column(db.Numeric(12, 3), nullable=True, default=Decimal("0.000"))
    reste_a_payer: Mapped[Decimal] = mapped_column(db.Numeric(12, 3), nullable=False)
    commission_plateforme: Mapped[Decimal] = mapped_column(db.Numeric(10, 3), nullable=False, default=Decimal("0.000"))
    commission_agence: Mapped[Decimal | None] = mapped_column(db.Numeric(10, 3), nullable=True)
    frais_enregistrement: Mapped[Decimal | None] = mapped_column(db.Numeric(10, 3), nullable=True)

    mode_paiement: Mapped[ModePaiement] = mapped_column(
        db.Enum(ModePaiement, name="mode_paiement_enum", values_callable=_enum_values),
        nullable=False,
        default=ModePaiement.VIREMENT,
    )
    statut: Mapped[StatutTransaction] = mapped_column(
        db.Enum(StatutTransaction, name="statut_transaction", values_callable=_enum_values),
        nullable=False,
        default=StatutTransaction.EN_COURS,
        index=True,
    )

    date_transaction: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    date_signature: Mapped[date | None] = mapped_column(db.Date, nullable=True)
    notaire: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    reference_acte: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    observations: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    annonce = relationship("Annonce", backref=db.backref("transactions", cascade="all, delete-orphan", passive_deletes=True))
    vendeur = relationship("Utilisateur", foreign_keys=[vendeur_id], backref="transactions_vendeur")
    acheteur = relationship("Utilisateur", foreign_keys=[acheteur_id], backref="transactions_acheteur")
    paiements = relationship("Paiement", back_populates="transaction", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'objet TransactionImmo en dictionnaire JSON."""
        return {
            "id": self.id,
            "reference": self.reference,
            "annonce_id": self.annonce_id,
            "titre_annonce": self.annonce.titre if self.annonce else "Bien",
            "type_transaction": self.type_transaction.value if hasattr(self.type_transaction, "value") else str(self.type_transaction),
            "vendeur_id": self.vendeur_id,
            "vendeur_nom": f"{self.vendeur.prenom} {self.vendeur.nom}".strip() if self.vendeur else "Vendeur",
            "acheteur_id": self.acheteur_id,
            "acheteur_nom": f"{self.acheteur.prenom} {self.acheteur.nom}".strip() if self.acheteur else "Acheteur",
            "montant_total": float(self.montant_total) if self.montant_total is not None else 0.0,
            "acompte": float(self.acompte) if self.acompte is not None else 0.0,
            "reste_a_payer": float(self.reste_a_payer) if self.reste_a_payer is not None else 0.0,
            "commission_plateforme": float(self.commission_plateforme) if self.commission_plateforme is not None else 0.0,
            "commission_agence": float(self.commission_agence) if self.commission_agence is not None else None,
            "frais_enregistrement": float(self.frais_enregistrement) if self.frais_enregistrement is not None else None,
            "mode_paiement": self.mode_paiement.value if hasattr(self.mode_paiement, "value") else str(self.mode_paiement),
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "date_transaction": en_iso_utc(self.date_transaction),
            "date_signature": self.date_signature.isoformat() if self.date_signature else None,
            "notaire": self.notaire,
            "reference_acte": self.reference_acte,
            "observations": self.observations,
            "paiements": [p.to_dict() for p in (self.paiements or [])],
        }


class Paiement(db.Model):
    """Versement ou tranche de paiement lié à une transaction."""

    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    montant: Mapped[Decimal] = mapped_column(db.Numeric(12, 3), nullable=False)
    date_paiement: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    mode_paiement: Mapped[ModePaiement] = mapped_column(
        db.Enum(ModePaiement, name="mode_paiement_p_enum", values_callable=_enum_values),
        nullable=False,
        default=ModePaiement.VIREMENT,
    )
    reference_paiement: Mapped[str] = mapped_column(db.String(50), nullable=False)
    statut: Mapped[StatutPaiement] = mapped_column(
        db.Enum(StatutPaiement, name="statut_paiement", values_callable=_enum_values),
        nullable=False,
        default=StatutPaiement.VALIDE,
    )
    justificatif: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    transaction = relationship("TransactionImmo", back_populates="paiements")

    def to_dict(self) -> dict[str, Any]:
        """Convertit le paiement en dictionnaire."""
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "montant": float(self.montant) if self.montant is not None else 0.0,
            "date_paiement": en_iso_utc(self.date_paiement),
            "mode_paiement": self.mode_paiement.value if hasattr(self.mode_paiement, "value") else str(self.mode_paiement),
            "reference_paiement": self.reference_paiement,
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "justificatif": self.justificatif,
        }
