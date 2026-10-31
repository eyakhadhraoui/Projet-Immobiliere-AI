"""Modèles SQLAlchemy du module « Gestion des annonces »."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db

if TYPE_CHECKING:
    from app.models.utilisateur import Utilisateur


def _utcnow() -> datetime:
    """Retourne l'instant courant en UTC.

    Returns:
        datetime: Date et heure courantes, avec fuseau UTC.
    """
    return datetime.now(timezone.utc)


def vers_utc(valeur: datetime | None) -> datetime | None:
    """Rend une date « consciente » du fuseau UTC (SQLite relit les dates sans fuseau).

    Args:
        valeur: Date enregistrée en UTC, avec ou sans fuseau, ou ``None``.

    Returns:
        datetime | None: La même date avec ``tzinfo=UTC``, ou ``None``.
    """
    if valeur is None or valeur.tzinfo is not None:
        return valeur
    return valeur.replace(tzinfo=timezone.utc)


def en_iso_utc(valeur: datetime | None) -> str | None:
    """Sérialise une date en ISO 8601 avec le fuseau UTC explicite (``+00:00``).

    SQLite relit les dates sans fuseau : elles sont enregistrées en UTC, on le rétablit
    pour que le navigateur ne les interprète pas comme des heures locales.

    Args:
        valeur: Date à sérialiser (avec ou sans fuseau), ou ``None``.

    Returns:
        str | None: Date ISO 8601, ou ``None``.
    """
    valeur = vers_utc(valeur)
    return valeur.isoformat() if valeur is not None else None


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Liste les valeurs d'un Enum pour les stocker telles quelles en base.

    Args:
        enum_cls: Classe Enum à convertir.

    Returns:
        list[str]: Valeurs des membres de l'Enum.
    """
    return [member.value for member in enum_cls]


class TypeBien(enum.StrEnum):
    """Type de bien immobilier."""

    APPARTEMENT = "appartement"
    MAISON = "maison"
    STUDIO = "studio"
    VILLA = "villa"
    RESIDENCE = "residence"


class Transaction(enum.StrEnum):
    """Type de transaction proposée."""

    VENTE = "vente"
    LOCATION = "location"


class StatutAnnonce(enum.StrEnum):
    """Cycle de vie d'une annonce."""

    BROUILLON = "brouillon"
    EN_ATTENTE = "en_attente"
    PUBLIEE = "publiee"
    LOUEE = "louee"
    VENDUE = "vendue"


class Annonce(db.Model):
    """Annonce immobilière publiée par un propriétaire.

    Attributes:
        owner_id: Propriétaire de l'annonce (clé étrangère vers ``utilisateurs``, USER-002).
        proprietaire: Compte propriétaire ; seuls son prénom et sa photo sont publiés.
        caracteristiques: Liste d'équipements, ex. ``["parking", "climatisation"]``.
        photos: Photos de l'annonce, triées par ``ordre``.
    """

    __tablename__ = "annonces"

    id: Mapped[int] = mapped_column(primary_key=True)
    titre: Mapped[str] = mapped_column(db.String(200), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    type_bien: Mapped[TypeBien] = mapped_column(
        db.Enum(TypeBien, name="type_bien", values_callable=_enum_values),
        nullable=False,
    )
    transaction: Mapped[Transaction] = mapped_column(
        db.Enum(Transaction, name="transaction", values_callable=_enum_values),
        nullable=False,
    )
    prix: Mapped[float] = mapped_column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    surface: Mapped[float] = mapped_column(db.Float, nullable=False)
    nb_pieces: Mapped[int] = mapped_column(db.Integer, nullable=False)
    meuble: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    adresse: Mapped[str] = mapped_column(db.String(255), nullable=False)
    ville: Mapped[str] = mapped_column(db.String(100), nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(db.Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(db.Float, nullable=True)
    caracteristiques: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    statut: Mapped[StatutAnnonce] = mapped_column(
        db.Enum(StatutAnnonce, name="statut_annonce", values_callable=_enum_values),
        nullable=False,
        default=StatutAnnonce.BROUILLON,
        server_default=StatutAnnonce.BROUILLON.value,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        db.ForeignKey("utilisateurs.id", name="fk_annonces_owner_id_utilisateurs"), nullable=False, index=True
    )
    motif_attente: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    revue_demandee_le: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    empreintes_refusees: Mapped[list[dict[str, str | None]]] = mapped_column(
        db.JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    proprietaire: Mapped[Utilisateur] = relationship(lazy="selectin")
    photos: Mapped[list[AnnoncePhoto]] = relationship(
        back_populates="annonce",
        order_by="AnnoncePhoto.ordre",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_photos: bool = True) -> dict[str, Any]:
        """Sérialise l'annonce en dictionnaire JSON-compatible.

        Args:
            include_photos: Inclure la liste des photos dans le résultat.

        Returns:
            dict[str, Any]: Représentation de l'annonce.
        """
        data: dict[str, Any] = {
            "id": self.id,
            "titre": self.titre,
            "description": self.description,
            "type_bien": self.type_bien.value if self.type_bien else None,
            "transaction": self.transaction.value if self.transaction else None,
            "prix": self.prix,
            "surface": self.surface,
            "nb_pieces": self.nb_pieces,
            "meuble": self.meuble,
            "adresse": self.adresse,
            "ville": self.ville,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "caracteristiques": self.caracteristiques or [],
            "statut": self.statut.value if self.statut else None,
            "owner_id": self.owner_id,
            # Informations publiques du propriétaire uniquement (ni nom, ni email, ni téléphone).
            "proprietaire": {
                "prenom": self.proprietaire.prenom,
                "photo_profil": self.proprietaire.photo_profil,
            } if self.proprietaire else None,
            "created_at": en_iso_utc(self.created_at),
            "updated_at": en_iso_utc(self.updated_at),
        }
        if include_photos:
            data["photos"] = [photo.to_dict() for photo in self.photos]
        return data

    def __repr__(self) -> str:
        return f"<Annonce {self.id} {self.titre!r}>"


class AnnoncePhoto(db.Model):
    """Photo rattachée à une annonce.

    Attributes:
        type_piece: Pièce représentée (cuisine, salon…), remplie plus tard par l'IA.
        ordre: Position d'affichage de la photo dans l'annonce.
    """

    __tablename__ = "annonce_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    annonce_id: Mapped[int] = mapped_column(
        db.ForeignKey("annonces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(db.String(500), nullable=False)
    type_piece: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    ordre: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    phash: Mapped[str | None] = mapped_column(db.String(16), nullable=True)

    annonce: Mapped[Annonce] = relationship(back_populates="photos")

    def to_dict(self) -> dict[str, Any]:
        """Sérialise la photo en dictionnaire JSON-compatible.

        Returns:
            dict[str, Any]: Représentation de la photo.
        """
        return {
            "id": self.id,
            "annonce_id": self.annonce_id,
            "url": self.url,
            "type_piece": self.type_piece,
            "ordre": self.ordre,
        }

    def __repr__(self) -> str:
        return f"<AnnoncePhoto {self.id} annonce={self.annonce_id} ordre={self.ordre}>"
