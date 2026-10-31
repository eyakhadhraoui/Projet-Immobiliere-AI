"""Persistance locale des dossiers et éléments de preuve locatifs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db


def _maintenant_utc() -> datetime:
    """Retourne l'heure UTC sans dépendre du fuseau de la machine."""
    return datetime.now(timezone.utc)


class DossierLitige(db.Model):
    """Dossier privé appartenant à un seul compte utilisateur."""

    __tablename__ = "dossiers_litige"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_dossiers_litige_case_id"),
        Index("ix_dossiers_litige_case_id", "case_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(db.String(32), nullable=False)
    proprietaire_id: Mapped[int] = mapped_column(
        db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    titre: Mapped[str] = mapped_column(db.String(160), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    langue: Mapped[str] = mapped_column(db.String(5), nullable=False, default="fr")
    juridiction: Mapped[str | None] = mapped_column(db.String(120), nullable=True)
    provenance: Mapped[str | None] = mapped_column(db.String(120), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_maintenant_utc)
    modifie_le: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_maintenant_utc, onupdate=_maintenant_utc
    )

    location = relationship("LocationImmo")
    documents: Mapped[list["DocumentLitige"]] = relationship(
        cascade="all, delete-orphan", order_by="DocumentLitige.cree_le"
    )
    questions: Mapped[list["QuestionLitige"]] = relationship(
        cascade="all, delete-orphan", order_by="QuestionLitige.cree_le"
    )
    rapports: Mapped[list["RapportLitige"]] = relationship(
        cascade="all, delete-orphan", order_by="RapportLitige.cree_le"
    )


class DocumentLitige(db.Model):
    """Document source stocké hors du répertoire public."""

    __tablename__ = "documents_litige"
    __table_args__ = (UniqueConstraint("case_id", "hash_fichier", name="uq_litige_document_hash_case"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(
        db.ForeignKey("dossiers_litige.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom_fichier: Mapped[str] = mapped_column(db.String(255), nullable=False)
    nom_stocke: Mapped[str] = mapped_column(db.String(80), nullable=False, unique=True)
    titre: Mapped[str] = mapped_column(db.String(255), nullable=False)
    auteur: Mapped[str | None] = mapped_column(db.String(160), nullable=True)
    role_auteur: Mapped[str] = mapped_column(db.String(32), nullable=False, default="unknown")
    date_document: Mapped[date | None] = mapped_column(db.Date, nullable=True)
    texte_extrait: Mapped[str] = mapped_column(db.Text, nullable=False)
    hash_fichier: Mapped[str] = mapped_column(db.String(64), nullable=False)
    type_mime: Mapped[str] = mapped_column(db.String(120), nullable=False)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_maintenant_utc)

    passages: Mapped[list["PassageLitige"]] = relationship(
        cascade="all, delete-orphan", order_by="PassageLitige.debut"
    )


class PassageLitige(db.Model):
    """Passage dont les offsets pointent dans le texte extrait exact du document."""

    __tablename__ = "passages_litige"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_passages_litige_chunk_id"),
        Index("ix_passages_litige_chunk_id", "chunk_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(
        db.ForeignKey("dossiers_litige.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        db.ForeignKey("documents_litige.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(db.String(40), nullable=False)
    texte: Mapped[str] = mapped_column(db.Text, nullable=False)
    debut: Mapped[int] = mapped_column(db.Integer, nullable=False)
    fin: Mapped[int] = mapped_column(db.Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(db.JSON, nullable=True)
    retrieval_metadata: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)

    classification: Mapped["ClassificationLitige | None"] = relationship(
        cascade="all, delete-orphan", uselist=False
    )
    dates: Mapped[list["DateLitige"]] = relationship(cascade="all, delete-orphan")
    annotations: Mapped[list["AnnotationLitige"]] = relationship(cascade="all, delete-orphan")


class ClassificationLitige(db.Model):
    """Étiquette indicative, toujours modifiable et soumise à revue humaine."""

    __tablename__ = "classifications_litige"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_classifications_litige_chunk_id"),
        Index("ix_classifications_litige_chunk_id", "chunk_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(db.ForeignKey("passages_litige.chunk_id", ondelete="CASCADE"), nullable=False)
    type_preuve: Mapped[str] = mapped_column(db.String(40), nullable=False)
    sujet: Mapped[str] = mapped_column(db.String(40), nullable=False, default="other")
    score: Mapped[float] = mapped_column(db.Float, nullable=False, default=0.0)
    revue_humaine: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    verifie_manuellement: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)


class DateLitige(db.Model):
    """Date explicitement lue dans un passage, sans assertion de véracité."""

    __tablename__ = "dates_litige"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(
        db.ForeignKey("passages_litige.chunk_id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_normalisee: Mapped[date] = mapped_column(db.Date, nullable=False, index=True)
    texte_source: Mapped[str] = mapped_column(db.String(1000), nullable=False)
    attribution: Mapped[str] = mapped_column(db.String(32), nullable=False, default="unknown")
    verifiee: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)


class AnnotationLitige(db.Model):
    """Annotation humaine sur un passage."""

    __tablename__ = "annotations_litige"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(
        db.ForeignKey("passages_litige.chunk_id", ondelete="CASCADE"), nullable=False, index=True
    )
    auteur_id: Mapped[int] = mapped_column(
        db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    etiquette: Mapped[str] = mapped_column(db.String(80), nullable=False)
    valeur: Mapped[str] = mapped_column(db.Text, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_maintenant_utc)


class QuestionLitige(db.Model):
    """Question factuelle enregistrée avec son statut prudent et ses sources."""

    __tablename__ = "questions_litige"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(
        db.ForeignKey("dossiers_litige.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(db.String(1000), nullable=False)
    answer_status: Mapped[str] = mapped_column(db.String(40), nullable=False)
    answer: Mapped[str] = mapped_column(db.Text, nullable=False)
    value: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_maintenant_utc)

    citations: Mapped[list["CitationLitige"]] = relationship(cascade="all, delete-orphan")


class CitationLitige(db.Model):
    """Citation contrôlée comme sous-chaîne littérale de sa source."""

    __tablename__ = "citations_litige"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        db.ForeignKey("questions_litige.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(
        db.ForeignKey("passages_litige.chunk_id", ondelete="CASCADE"), nullable=False, index=True
    )
    citation: Mapped[str] = mapped_column(db.Text, nullable=False)


class RapportLitige(db.Model):
    """Instantané local d'un rapport exportable."""

    __tablename__ = "rapports_litige"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_rapports_litige_report_id"),
        Index("ix_rapports_litige_report_id", "report_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(db.String(32), nullable=False)
    case_id: Mapped[str] = mapped_column(
        db.ForeignKey("dossiers_litige.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(db.String(12), nullable=False)
    contenu: Mapped[str] = mapped_column(db.Text, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_maintenant_utc)
