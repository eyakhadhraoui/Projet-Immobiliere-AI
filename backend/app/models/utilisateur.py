"""Modèles du module « Gestion des utilisateurs » : comptes, historique, tentatives de connexion."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column, validates
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models.annonce import _enum_values, _utcnow, en_iso_utc


class RoleUtilisateur(enum.StrEnum):
    """Rôle d'un compte (choisi à l'inscription, non modifiable ensuite par l'utilisateur)."""

    CLIENT = "client"
    PROPRIETAIRE = "proprietaire"


def masquer_cin(cin: str | None) -> str | None:
    """Masque un numéro de CIN en ne gardant que les 2 derniers chiffres.

    Args:
        cin: Numéro complet, ou ``None``.

    Returns:
        str | None: Ex. ``"******78"``, ou ``None`` si aucun numéro.
    """
    if not cin:
        return None
    return "*" * (len(cin) - 2) + cin[-2:]


class Utilisateur(db.Model):
    """Compte utilisateur.

    Attributes:
        mot_de_passe_hash: Hash (scrypt, via Werkzeug) ; le mot de passe n'est jamais stocké en clair.
        cin_numero: Numéro de CIN complet ; jamais renvoyé par l'API (voir ``to_dict``).
        cin_verifiee: Vérification de la CIN (future fonctionnalité d'IA) ; non modifiable par l'utilisateur.
        visage_verifie: Vérification du visage (future fonctionnalité d'IA) ; non modifiable par l'utilisateur.
        jeton_version: Incrémenté au changement de mot de passe : les jetons émis avant deviennent invalides.
    """

    __tablename__ = "utilisateurs"
    __table_args__ = (db.UniqueConstraint("cin_numero", name="uq_utilisateurs_cin_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(db.String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(254), nullable=False, unique=True, index=True)
    telephone: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[RoleUtilisateur] = mapped_column(
        db.Enum(RoleUtilisateur, name="role_utilisateur", values_callable=_enum_values),
        nullable=False,
        default=RoleUtilisateur.CLIENT,
    )
    date_naissance: Mapped[date | None] = mapped_column(db.Date, nullable=True)
    ville: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    adresse: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    photo_profil: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    cin_numero: Mapped[str | None] = mapped_column(db.String(8), nullable=True)
    cin_verifiee: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    visage_verifie: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    derniere_connexion: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    jeton_version: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    @validates("email")
    def _normaliser_email(self, _cle: str, valeur: str) -> str:
        """Enregistre toujours l'email sans espaces et en minuscules (unicité insensible à la casse).

        Args:
            _cle: Nom de l'attribut (``email``).
            valeur: Email fourni.

        Returns:
            str: Email normalisé.
        """
        return valeur.strip().lower()

    def definir_mot_de_passe(self, mot_de_passe: str) -> None:
        """Hache et enregistre un mot de passe.

        Args:
            mot_de_passe: Mot de passe en clair (déjà validé par le schéma).
        """
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe: str) -> bool:
        """Compare un mot de passe au hash enregistré.

        Args:
            mot_de_passe: Mot de passe en clair.

        Returns:
            bool: ``True`` s'il correspond.
        """
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le compte pour l'API, sans le hash du mot de passe ni la CIN complète.

        Returns:
            dict[str, Any]: Représentation publique du compte de l'utilisateur connecté.
        """
        return {
            "id": self.id,
            "nom": self.nom,
            "prenom": self.prenom,
            "email": self.email,
            "telephone": self.telephone,
            "role": self.role.value,
            "date_naissance": self.date_naissance.isoformat() if self.date_naissance else None,
            "ville": self.ville,
            "adresse": self.adresse,
            "photo_profil": self.photo_profil,
            "cin_numero": masquer_cin(self.cin_numero),
            "cin_verifiee": self.cin_verifiee,
            "visage_verifie": self.visage_verifie,
            "derniere_connexion": en_iso_utc(self.derniere_connexion),
            "created_at": en_iso_utc(self.created_at),
            "updated_at": en_iso_utc(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Utilisateur {self.id} {self.role}>"


class ActionUtilisateur(enum.StrEnum):
    """Types d'action enregistrés dans l'historique des utilisateurs."""

    CREATION = "creation"
    MODIFICATION = "modification"
    CHANGEMENT_MOT_DE_PASSE = "changement_mot_de_passe"
    SUPPRESSION = "suppression"
    CONNEXION_REUSSIE = "connexion_reussie"
    CONNEXION_ECHOUEE = "connexion_echouee"


class UtilisateurHistorique(db.Model):
    """Action sur un compte utilisateur.

    ``utilisateur_id`` n'est pas une clé étrangère (historique conservé après suppression du compte) et peut être
    vide pour une connexion échouée avec un email inconnu ; ``email`` garde l'email au moment de l'action.
    Les détails ne contiennent jamais de mot de passe ni de CIN complète.
    """

    __tablename__ = "utilisateur_historique"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True, index=True)
    email: Mapped[str] = mapped_column(db.String(254), nullable=False, index=True)
    action: Mapped[ActionUtilisateur] = mapped_column(
        db.Enum(ActionUtilisateur, name="action_utilisateur", values_callable=_enum_values),
        nullable=False,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    adresse_ip: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    def to_dict(self) -> dict[str, Any]:
        """Sérialise l'entrée d'historique.

        Returns:
            dict[str, Any]: Représentation de l'entrée.
        """
        return {
            "id": self.id,
            "utilisateur_id": self.utilisateur_id,
            "email": self.email,
            "action": self.action.value,
            "details": self.details or {},
            "adresse_ip": self.adresse_ip,
            "created_at": en_iso_utc(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<UtilisateurHistorique {self.id} {self.action}>"


class TentativeConnexion(db.Model):
    """Compteur d'échecs de connexion par email (que le compte existe ou non).

    Indexé par email et non par compte : le blocage se comporte de la même façon pour un email inconnu,
    ce qui empêche de deviner quels emails ont un compte.
    """

    __tablename__ = "tentatives_connexion"

    email: Mapped[str] = mapped_column(db.String(254), primary_key=True)
    nb_echecs: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    dernier_echec: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    bloque_jusqu_a: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TentativeConnexion {self.nb_echecs} échec(s)>"


class EvenementConnexion(db.Model):
    """Événement de connexion conservé pour l'analyse de risque, sans IP en clair."""

    __tablename__ = "evenements_connexion"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reussie: Mapped[bool] = mapped_column(db.Boolean, nullable=False, index=True)
    heure_utc: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    navigateur: Mapped[str] = mapped_column(db.String(40), nullable=False, default="inconnu")
    appareil: Mapped[str] = mapped_column(db.String(24), nullable=False, default="inconnu")
    lieu_approximatif: Mapped[str | None] = mapped_column(db.String(160), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    niveau_risque: Mapped[str] = mapped_column(db.String(16), nullable=False, default="faible")
    score_risque: Mapped[float] = mapped_column(db.Float, nullable=False, default=0.0)
    retour_utilisateur: Mapped[str | None] = mapped_column(db.String(12), nullable=True)


class VerificationConnexion(db.Model):
    """Défi temporaire e-mail émis avant de créer une session JWT à haut risque."""

    __tablename__ = "verifications_connexion"

    id: Mapped[int] = mapped_column(primary_key=True)
    jeton_hash: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    utilisateur_id: Mapped[int] = mapped_column(
        db.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evenement_id: Mapped[int] = mapped_column(
        db.ForeignKey("evenements_connexion.id", ondelete="CASCADE"), nullable=False
    )
    expire_le: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    nb_echecs: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    utilise_le: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
