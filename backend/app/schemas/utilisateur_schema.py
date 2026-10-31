"""Schémas Marshmallow du module utilisateurs.

Les champs inconnus sont refusés (``SchemaFr``) : un utilisateur ne peut donc pas envoyer ``role`` dans la
modification de son profil, ni ``cin_verifiee`` / ``visage_verifie`` (réservés à la future vérification par IA).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from marshmallow import ValidationError, fields, pre_load, validate, validates_schema

from app.models import RoleUtilisateur
from app.schemas.annonce_schema import MESSAGES, MESSAGES_ENUM, SchemaFr

LONGUEUR_MIN_MOT_DE_PASSE = 8
LONGUEUR_MAX_MOT_DE_PASSE = 128  # borne le coût du hachage


def valider_mot_de_passe(valeur: str) -> None:
    """Vérifie la politique de mot de passe : 8 caractères minimum, avec au moins une lettre et un chiffre.

    Args:
        valeur: Mot de passe en clair.

    Raises:
        ValidationError: Si une règle n'est pas respectée (tous les messages sont renvoyés).
    """
    erreurs = []
    if len(valeur) < LONGUEUR_MIN_MOT_DE_PASSE:
        erreurs.append(f"Doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères.")
    if len(valeur) > LONGUEUR_MAX_MOT_DE_PASSE:
        erreurs.append(f"Doit contenir au plus {LONGUEUR_MAX_MOT_DE_PASSE} caractères.")
    if not re.search(r"[^\W\d_]", valeur):
        erreurs.append("Doit contenir au moins une lettre.")
    if not re.search(r"\d", valeur):
        erreurs.append("Doit contenir au moins un chiffre.")
    if erreurs:
        raise ValidationError(erreurs)


def valider_date_naissance(valeur: date) -> None:
    """Refuse une date de naissance future ou antérieure à 1900.

    Args:
        valeur: Date de naissance.

    Raises:
        ValidationError: Si la date est hors limites.
    """
    if valeur > date.today():
        raise ValidationError("Ne peut pas être dans le futur.")
    if valeur.year < 1900:
        raise ValidationError("Date invalide.")


def _texte(longueur_max: int, **options: Any) -> fields.String:
    """Champ texte de 1 à ``longueur_max`` caractères, avec messages en français.

    Args:
        longueur_max: Longueur maximale.
        **options: Options passées à ``fields.String`` (``required``, ``allow_none``…).

    Returns:
        fields.String: Champ configuré.
    """
    return fields.String(
        validate=validate.Length(min=1, max=longueur_max, error="Doit contenir entre {min} et {max} caractères."),
        error_messages=MESSAGES,
        **options,
    )


class SchemaUtilisateurFr(SchemaFr):
    """Base : retire les espaces en début et fin des champs texte (sauf mots de passe)."""

    CHAMPS_NON_NETTOYES = frozenset({"mot_de_passe", "ancien_mot_de_passe", "nouveau_mot_de_passe"})

    @pre_load
    def nettoyer(self, data: Any, **kwargs: Any) -> Any:
        """Supprime les espaces superflus des chaînes ; une chaîne vide devient ``None``.

        Args:
            data: Corps JSON reçu.
            **kwargs: Arguments transmis par Marshmallow.

        Returns:
            Any: Données nettoyées (inchangées si ce n'est pas un objet).
        """
        if not isinstance(data, dict):
            return data
        return {
            cle: (valeur.strip() or None) if isinstance(valeur, str) and cle not in self.CHAMPS_NON_NETTOYES else valeur
            for cle, valeur in data.items()
        }


class ChampsProfil(SchemaUtilisateurFr):
    """Champs du profil modifiables par l'utilisateur."""

    nom = _texte(100, required=True)
    prenom = _texte(100, required=True)
    email = fields.Email(
        required=True,
        validate=validate.Length(max=254, error="Doit contenir au plus {max} caractères."),
        error_messages={**MESSAGES, "invalid": "Adresse email invalide."},
    )
    telephone = fields.String(
        allow_none=True,
        validate=validate.Regexp(r"^\+?[0-9 ]{8,20}$", error="Numéro de téléphone invalide."),
        error_messages=MESSAGES,
    )
    date_naissance = fields.Date(
        allow_none=True,
        validate=valider_date_naissance,
        error_messages={**MESSAGES, "invalid": "Date invalide (format attendu : AAAA-MM-JJ)."},
    )
    ville = _texte(100, allow_none=True)
    adresse = _texte(255, allow_none=True)
    cin_numero = fields.String(
        allow_none=True,
        validate=validate.Regexp(r"^\d{8}$", error="La CIN doit contenir exactement 8 chiffres."),
        error_messages=MESSAGES,
    )


class InscriptionSchema(ChampsProfil):
    """Valide ``POST /api/auth/inscription``. Le rôle est client ou propriétaire (client par défaut)."""

    mot_de_passe = fields.String(required=True, validate=valider_mot_de_passe, error_messages=MESSAGES)
    role = fields.Enum(
        RoleUtilisateur, by_value=True, load_default=RoleUtilisateur.CLIENT, error_messages=MESSAGES_ENUM
    )


class ProfilSchema(ChampsProfil):
    """Valide ``PUT /api/auth/moi`` (à charger avec ``partial=True``) : ni rôle, ni mot de passe, ni vérifications."""


class ConnexionSchema(SchemaUtilisateurFr):
    """Valide ``POST /api/auth/connexion`` (pas de validation du format : même réponse pour tout email)."""

    email = fields.String(required=True, error_messages=MESSAGES)
    mot_de_passe = fields.String(required=True, error_messages=MESSAGES)


class ChangementMotDePasseSchema(SchemaUtilisateurFr):
    """Valide ``PUT /api/auth/moi/mot-de-passe``."""

    ancien_mot_de_passe = fields.String(required=True, error_messages=MESSAGES)
    nouveau_mot_de_passe = fields.String(required=True, validate=valider_mot_de_passe, error_messages=MESSAGES)

    @validates_schema
    def verifier_difference(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Refuse un nouveau mot de passe identique à l'ancien.

        Args:
            data: Données déjà validées champ par champ.
            **kwargs: Arguments transmis par Marshmallow.

        Raises:
            ValidationError: Si les deux mots de passe sont identiques.
        """
        if data.get("ancien_mot_de_passe") == data.get("nouveau_mot_de_passe"):
            raise ValidationError("Doit être différent de l'ancien mot de passe.", field_name="nouveau_mot_de_passe")


class SuppressionCompteSchema(SchemaUtilisateurFr):
    """Valide ``DELETE /api/auth/moi`` : le mot de passe confirme la suppression."""

    mot_de_passe = fields.String(required=True, error_messages=MESSAGES)
