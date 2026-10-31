"""Logique métier des comptes utilisateurs : inscription, connexion, profil, mot de passe, photo, suppression.

Comme pour les annonces, chaque action enregistre son entrée d'historique dans la même transaction
(un seul ``commit``). L'historique ne contient jamais de mot de passe ni de CIN complète.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from marshmallow import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.errors import Conflit, IdentifiantsInvalides, TropDeTentatives
from app.models import (
    ActionUtilisateur,
    Annonce,
    TentativeConnexion,
    Utilisateur,
    UtilisateurHistorique,
)
from app.models.annonce import vers_utc
from app.models.utilisateur import masquer_cin
from app.services.annonce_service import preparer_suppression
from app.services.historique_service import differences
from app.services.photo_service import controler_image, enregistrer_fichier, supprimer_fichiers

MAX_ECHECS_CONNEXION = 5
DUREE_BLOCAGE = timedelta(minutes=15)
MESSAGE_EMAIL_UTILISE = "Un compte existe déjà avec cet email."
MESSAGE_CIN_UTILISEE = "Cette CIN est déjà associée à un compte."
MESSAGE_BLOCAGE = "Trop de tentatives de connexion. Réessayez dans 15 minutes."

# Hash calculé une fois : vérifié quand l'email est inconnu, pour que la réponse prenne le même temps
# que pour un compte existant (sinon la durée révélerait quels emails ont un compte).
_HASH_FACTICE = generate_password_hash("compte-inexistant-0")


def _maintenant() -> datetime:
    """Instant courant en UTC.

    Returns:
        datetime: Date et heure courantes.
    """
    return datetime.now(timezone.utc)


def normaliser_email(email: str) -> str:
    """Email sans espaces et en minuscules (même règle que le modèle).

    Args:
        email: Email saisi.

    Returns:
        str: Email normalisé.
    """
    return email.strip().lower()


def _journaliser(
    action: ActionUtilisateur,
    email: str,
    utilisateur_id: int | None,
    details: dict[str, Any] | None = None,
    adresse_ip: str | None = None,
) -> None:
    """Ajoute une entrée à l'historique des utilisateurs, sans commit.

    Args:
        action: Type d'action.
        email: Email concerné (connu même si le compte n'existe pas).
        utilisateur_id: Identifiant du compte, ou ``None`` (email inconnu).
        details: Détails de l'action (jamais de mot de passe ni de CIN complète).
        adresse_ip: Adresse IP de la requête.
    """
    db.session.add(UtilisateurHistorique(
        utilisateur_id=utilisateur_id,
        email=email,
        action=action,
        details=details or {},
        adresse_ip=adresse_ip,
    ))


def _email_pris(email: str, sauf_id: int | None = None) -> bool:
    """Indique si un autre compte utilise déjà cet email.

    Args:
        email: Email normalisé.
        sauf_id: Compte à ignorer (l'utilisateur qui modifie son propre email).

    Returns:
        bool: ``True`` si l'email est déjà utilisé.
    """
    requete = select(Utilisateur.id).where(Utilisateur.email == email)
    if sauf_id is not None:
        requete = requete.where(Utilisateur.id != sauf_id)
    return db.session.scalar(requete) is not None


def _cin_prise(cin: str | None, sauf_id: int | None = None) -> bool:
    """Indique si un autre compte utilise déjà ce numéro de CIN.

    Args:
        cin: Numéro de CIN, ou ``None``.
        sauf_id: Compte à ignorer.

    Returns:
        bool: ``True`` si la CIN est déjà utilisée.
    """
    if not cin:
        return False
    requete = select(Utilisateur.id).where(Utilisateur.cin_numero == cin)
    if sauf_id is not None:
        requete = requete.where(Utilisateur.id != sauf_id)
    return db.session.scalar(requete) is not None


def _valider_unicite(email: str | None, cin: str | None, sauf_id: int | None = None) -> None:
    """Refuse un email ou une CIN déjà utilisés par un autre compte.

    Args:
        email: Email normalisé, ou ``None`` s'il ne change pas.
        cin: Numéro de CIN, ou ``None``.
        sauf_id: Compte à ignorer.

    Raises:
        Conflit: Si l'email ou la CIN sont déjà utilisés (409).
    """
    if email is not None and _email_pris(email, sauf_id):
        raise Conflit(MESSAGE_EMAIL_UTILISE)
    if _cin_prise(cin, sauf_id):
        raise Conflit(MESSAGE_CIN_UTILISEE)


def _conflit(erreur: IntegrityError) -> Conflit:
    """Annule la transaction et traduit une violation d'unicité en 409.

    Cas d'une requête concurrente qui a pris l'email ou la CIN entre la vérification et l'écriture :
    c'est alors la contrainte d'unicité de la base qui refuse (au ``flush`` ou au ``commit``).

    Args:
        erreur: Erreur levée par la base.

    Returns:
        Conflit: Exception 409 à lever.
    """
    db.session.rollback()
    message = MESSAGE_CIN_UTILISEE if "cin_numero" in str(erreur.orig) else MESSAGE_EMAIL_UTILISE
    return Conflit(message)


def creer_compte(donnees: dict[str, Any], adresse_ip: str | None = None) -> Utilisateur:
    """Crée un compte (inscription).

    Args:
        donnees: Champs validés par ``InscriptionSchema`` (dont ``mot_de_passe`` en clair).
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte créé.

    Raises:
        Conflit: Si l'email ou la CIN sont déjà utilisés (409).
    """
    donnees = dict(donnees)
    mot_de_passe = donnees.pop("mot_de_passe")
    donnees["email"] = normaliser_email(donnees["email"])
    _valider_unicite(donnees["email"], donnees.get("cin_numero"))

    utilisateur = Utilisateur(**donnees)
    utilisateur.definir_mot_de_passe(mot_de_passe)
    try:
        db.session.add(utilisateur)
        db.session.flush()  # attribue l'identifiant, repris dans l'historique
        _journaliser(ActionUtilisateur.CREATION, utilisateur.email, utilisateur.id,
                     {"role": utilisateur.role.value}, adresse_ip)
        db.session.commit()
    except IntegrityError as erreur:
        raise _conflit(erreur) from erreur
    return utilisateur


def authentifier(email: str, mot_de_passe: str, adresse_ip: str | None = None) -> Utilisateur:
    """Vérifie les identifiants, avec blocage temporaire après ``MAX_ECHECS_CONNEXION`` échecs.

    La réponse est la même que l'email existe ou non : même message, même blocage (compteur par email),
    et un hash est vérifié dans tous les cas (temps de réponse comparable).

    Args:
        email: Email saisi.
        mot_de_passe: Mot de passe saisi.
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte authentifié (dernière connexion mise à jour).

    Raises:
        TropDeTentatives: Si l'email est bloqué, ou au moment où il le devient (429).
        IdentifiantsInvalides: Si l'email ou le mot de passe est incorrect (401).
    """
    email = normaliser_email(email)
    maintenant = _maintenant()
    tentative = db.session.get(TentativeConnexion, email)
    utilisateur = db.session.scalar(select(Utilisateur).where(Utilisateur.email == email))
    utilisateur_id = utilisateur.id if utilisateur else None

    if tentative and tentative.bloque_jusqu_a and vers_utc(tentative.bloque_jusqu_a) > maintenant:
        _journaliser(ActionUtilisateur.CONNEXION_ECHOUEE, email, utilisateur_id, {"raison": "blocage_en_cours"}, adresse_ip)
        db.session.commit()
        raise TropDeTentatives(MESSAGE_BLOCAGE)

    if utilisateur is not None:
        valide = utilisateur.verifier_mot_de_passe(mot_de_passe)
    else:
        check_password_hash(_HASH_FACTICE, mot_de_passe)  # même coût, résultat ignoré
        valide = False

    if not valide:
        if tentative is None:
            tentative = TentativeConnexion(email=email, nb_echecs=0)
            db.session.add(tentative)
        elif tentative.bloque_jusqu_a is not None:  # blocage précédent terminé : on repart de zéro
            tentative.nb_echecs = 0
            tentative.bloque_jusqu_a = None
        tentative.nb_echecs += 1
        tentative.dernier_echec = maintenant
        bloque = tentative.nb_echecs >= MAX_ECHECS_CONNEXION
        if bloque:
            tentative.bloque_jusqu_a = maintenant + DUREE_BLOCAGE
        _journaliser(ActionUtilisateur.CONNEXION_ECHOUEE, email, utilisateur_id,
                     {"raison": "identifiants_invalides", "nb_echecs": tentative.nb_echecs, "bloque": bloque},
                     adresse_ip)
        db.session.commit()
        if bloque:
            raise TropDeTentatives(MESSAGE_BLOCAGE)
        raise IdentifiantsInvalides()

    if tentative is not None:
        db.session.delete(tentative)
    utilisateur.derniere_connexion = maintenant
    _journaliser(ActionUtilisateur.CONNEXION_REUSSIE, email, utilisateur.id, None, adresse_ip)
    db.session.commit()
    return utilisateur


def modifier_profil(utilisateur: Utilisateur, donnees: dict[str, Any], adresse_ip: str | None = None) -> Utilisateur:
    """Modifie le profil de l'utilisateur connecté (ni rôle, ni mot de passe : refusés par le schéma).

    Changer de numéro de CIN annule la vérification de la CIN.

    Args:
        utilisateur: Compte connecté.
        donnees: Champs validés par ``ProfilSchema`` (chargement partiel).
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte modifié.

    Raises:
        Conflit: Si le nouvel email ou la nouvelle CIN sont déjà utilisés (409).
    """
    donnees = dict(donnees)
    if "email" in donnees:
        donnees["email"] = normaliser_email(donnees["email"])
    _valider_unicite(donnees.get("email"), donnees.get("cin_numero"), sauf_id=utilisateur.id)

    modifications = differences(utilisateur, donnees)
    if "cin_numero" in modifications:
        modifications["cin_numero"] = {
            "avant": masquer_cin(modifications["cin_numero"]["avant"]),
            "apres": masquer_cin(modifications["cin_numero"]["apres"]),
        }
        if utilisateur.cin_verifiee:
            donnees["cin_verifiee"] = False
            modifications["cin_verifiee"] = {"avant": True, "apres": False}
    for champ, valeur in donnees.items():
        setattr(utilisateur, champ, valeur)
    try:
        if modifications:
            _journaliser(ActionUtilisateur.MODIFICATION, utilisateur.email, utilisateur.id, modifications, adresse_ip)
        db.session.commit()
    except IntegrityError as erreur:
        raise _conflit(erreur) from erreur
    return utilisateur


def changer_mot_de_passe(
    utilisateur: Utilisateur, ancien: str, nouveau: str, adresse_ip: str | None = None
) -> Utilisateur:
    """Change le mot de passe et invalide toutes les sessions ouvertes avec l'ancien.

    Args:
        utilisateur: Compte connecté.
        ancien: Mot de passe actuel (obligatoire).
        nouveau: Nouveau mot de passe (déjà validé par le schéma).
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte, avec ``jeton_version`` incrémenté.

    Raises:
        ValidationError: Si l'ancien mot de passe est incorrect (400).
    """
    if not utilisateur.verifier_mot_de_passe(ancien):
        raise ValidationError({"ancien_mot_de_passe": ["Mot de passe incorrect."]})
    utilisateur.definir_mot_de_passe(nouveau)
    utilisateur.jeton_version += 1
    _journaliser(ActionUtilisateur.CHANGEMENT_MOT_DE_PASSE, utilisateur.email, utilisateur.id, None, adresse_ip)
    db.session.commit()
    return utilisateur


def definir_photo(utilisateur: Utilisateur, fichier: FileStorage | None, adresse_ip: str | None = None) -> Utilisateur:
    """Remplace la photo de profil (mêmes contrôles que les photos d'annonces).

    Args:
        utilisateur: Compte connecté.
        fichier: Fichier du champ ``photo``.
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte avec sa nouvelle photo.

    Raises:
        ValidationError: Si aucun fichier n'est envoyé ou si ce n'est pas une image autorisée (400).
    """
    if fichier is None or not fichier.filename:
        raise ValidationError({"photo": ["Une photo est requise."]})
    extension, erreur = controler_image(fichier)
    if erreur:
        raise ValidationError({"photo": [erreur]})

    chemin, url = enregistrer_fichier(fichier, extension)
    ancienne = utilisateur.photo_profil
    try:
        utilisateur.photo_profil = url
        _journaliser(ActionUtilisateur.MODIFICATION, utilisateur.email, utilisateur.id,
                     {"photo_profil": {"avant": ancienne, "apres": url}}, adresse_ip)
        db.session.commit()
    except Exception:
        db.session.rollback()
        chemin.unlink(missing_ok=True)
        raise
    if ancienne:
        supprimer_fichiers([ancienne])
    return utilisateur


def supprimer_photo(utilisateur: Utilisateur, adresse_ip: str | None = None) -> Utilisateur:
    """Retire la photo de profil (sans effet s'il n'y en a pas).

    Args:
        utilisateur: Compte connecté.
        adresse_ip: Adresse IP de la requête.

    Returns:
        Utilisateur: Le compte sans photo.
    """
    ancienne = utilisateur.photo_profil
    if ancienne is None:
        return utilisateur
    utilisateur.photo_profil = None
    _journaliser(ActionUtilisateur.MODIFICATION, utilisateur.email, utilisateur.id,
                 {"photo_profil": {"avant": ancienne, "apres": None}}, adresse_ip)
    db.session.commit()
    supprimer_fichiers([ancienne])
    return utilisateur


def supprimer_compte(utilisateur: Utilisateur, mot_de_passe: str, adresse_ip: str | None = None) -> None:
    """Supprime le compte, sa photo, et les annonces dont il est propriétaire (avec leurs photos).

    Tout est fait dans une seule transaction ; l'historique (utilisateur et annonces) est conservé.
    Les fichiers sont supprimés du disque après le commit.

    Args:
        utilisateur: Compte connecté.
        mot_de_passe: Mot de passe actuel (confirmation obligatoire).
        adresse_ip: Adresse IP de la requête.

    Raises:
        ValidationError: Si le mot de passe est incorrect (400).
    """
    if not utilisateur.verifier_mot_de_passe(mot_de_passe):
        raise ValidationError({"mot_de_passe": ["Mot de passe incorrect."]})

    annonces = db.session.scalars(select(Annonce).where(Annonce.owner_id == utilisateur.id)).all()
    urls: list[str] = []
    for annonce in annonces:
        urls.extend(preparer_suppression(annonce))
    if utilisateur.photo_profil:
        urls.append(utilisateur.photo_profil)

    _journaliser(ActionUtilisateur.SUPPRESSION, utilisateur.email, utilisateur.id,
                 {"role": utilisateur.role.value, "nb_annonces_supprimees": len(annonces)}, adresse_ip)
    db.session.delete(utilisateur)
    db.session.commit()
    supprimer_fichiers(urls)
