"""Modèles du module « Gestion des réclamations » (signalements, litiges et modération)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc

if TYPE_CHECKING:
    from app.models.annonce import Annonce
    from app.models.utilisateur import Utilisateur


class TypeReclamation(enum.StrEnum):
    """Catégories de réclamation."""

    FAUSSE_ANNONCE = "fausse_annonce"
    PRIX_INCORRECT = "prix_incorrect"
    PHOTOS_TROMPEUSES = "photos_trompeuses"
    BIEN_DEJA_LOUE_VENDU = "bien_deja_loue_vendu"
    COMPORTEMENT_PROPRIETAIRE = "comportement_proprietaire"
    CONTENU_INAPPROPRIE = "contenu_inapproprie"
    PROBLEME_TECHNIQUE = "probleme_technique"
    AUTRE = "autre"


class StatutReclamation(enum.StrEnum):
    """Cycle de traitement d'une réclamation."""

    NOUVELLE = "nouvelle"
    EN_COURS = "en_cours"
    EN_ATTENTE_INFO = "en_attente_info"
    RESOLUE = "resolue"
    REJETEE = "rejetee"
    CLOTUREE = "cloturee"


class PrioriteReclamation(enum.StrEnum):
    """Niveau de priorité."""

    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"
    URGENTE = "urgente"


class DecisionReclamation(enum.StrEnum):
    """Décision ou sanction prise par l'administration."""

    AUCUNE_ACTION = "aucune_action"
    AVERTISSEMENT = "avertissement"
    ANNONCE_SUSPENDUE = "annonce_suspendue"
    ANNONCE_SUPPRIMEE = "annonce_supprimee"
    COMPTE_SUSPENDU = "compte_suspendu"
    COMPTE_BANNI = "compte_banni"


class Reclamation(db.Model):
    """Signalement ou plainte déposée par un utilisateur."""

    __tablename__ = "reclamations"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    annonce_id: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("annonces.id", ondelete="SET NULL"), nullable=True, index=True)
    utilisateur_vise_id: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True)

    type: Mapped[TypeReclamation] = mapped_column(
        db.Enum(TypeReclamation, name="type_reclamation_enum", values_callable=_enum_values),
        nullable=False,
        default=TypeReclamation.FAUSSE_ANNONCE,
    )
    objet: Mapped[str] = mapped_column(db.String(150), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)

    statut: Mapped[StatutReclamation] = mapped_column(
        db.Enum(StatutReclamation, name="statut_reclamation_enum", values_callable=_enum_values),
        nullable=False,
        default=StatutReclamation.NOUVELLE,
        index=True,
    )
    priorite: Mapped[PrioriteReclamation] = mapped_column(
        db.Enum(PrioriteReclamation, name="priorite_reclamation_enum", values_callable=_enum_values),
        nullable=False,
        default=PrioriteReclamation.NORMALE,
    )
    pieces_jointes: Mapped[list[str | dict[str, str]]] = mapped_column(db.JSON, nullable=False, default=list)

    traite_par: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    reponse_admin: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    decision: Mapped[DecisionReclamation | None] = mapped_column(
        db.Enum(DecisionReclamation, name="decision_reclamation_enum", values_callable=_enum_values),
        nullable=True,
    )

    date_creation: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    date_traitement: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    date_cloture: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    user = relationship("Utilisateur", foreign_keys=[user_id], backref="reclamations_deposees")
    annonce = relationship("Annonce", backref=db.backref("reclamations", cascade="all, delete-orphan", passive_deletes=True))
    utilisateur_vise = relationship("Utilisateur", foreign_keys=[utilisateur_vise_id], backref="reclamations_visant")
    admin_responsable = relationship("Utilisateur", foreign_keys=[traite_par])
    messages = relationship("ReclamationMessage", back_populates="reclamation", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'objet Reclamation en dictionnaire JSON."""
        return {
            "id": self.id,
            "reference": self.reference,
            "user_id": self.user_id,
            "auteur_nom": f"{self.user.prenom} {self.user.nom}".strip() if self.user else "Utilisateur",
            "auteur_email": self.user.email if self.user else "",
            "annonce_id": self.annonce_id,
            "titre_annonce": self.annonce.titre if self.annonce else None,
            "utilisateur_vise_id": self.utilisateur_vise_id,
            "utilisateur_vise_nom": f"{self.utilisateur_vise.prenom} {self.utilisateur_vise.nom}".strip() if self.utilisateur_vise else None,
            "type": self.type.value if hasattr(self.type, "value") else str(self.type),
            "objet": self.objet,
            "description": self.description,
            "statut": self.statut.value if hasattr(self.statut, "value") else str(self.statut),
            "priorite": self.priorite.value if hasattr(self.priorite, "value") else str(self.priorite),
            "pieces_jointes": self.pieces_jointes or [],
            "traite_par": self.traite_par,
            "reponse_admin": self.reponse_admin,
            "decision": self.decision.value if hasattr(self.decision, "value") and self.decision else (str(self.decision) if self.decision else None),
            "date_creation": en_iso_utc(self.date_creation),
            "date_traitement": en_iso_utc(self.date_traitement),
            "date_cloture": en_iso_utc(self.date_cloture),
            "messages": [m.to_dict() for m in (self.messages or [])],
        }


class ReclamationMessage(db.Model):
    """Message échangé dans le cadre d'une réclamation."""

    __tablename__ = "reclamation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    reclamation_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("reclamations.id", ondelete="CASCADE"), nullable=False, index=True)
    auteur_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(db.Text, nullable=False)
    date_envoi: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    reclamation = relationship("Reclamation", back_populates="messages")
    auteur = relationship("Utilisateur")

    def to_dict(self) -> dict[str, Any]:
        """Convertit le message en dictionnaire."""
        return {
            "id": self.id,
            "reclamation_id": self.reclamation_id,
            "auteur_id": self.auteur_id,
            "auteur_nom": f"{self.auteur.prenom} {self.auteur.nom}".strip() if self.auteur else "Utilisateur",
            "message": self.message,
            "date_envoi": en_iso_utc(self.date_envoi),
        }
