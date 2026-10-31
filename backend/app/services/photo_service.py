"""Logique métier des photos d'annonces : validation, enregistrement et suppression des fichiers."""

from __future__ import annotations

import uuid
import warnings
from collections.abc import Iterable
from pathlib import Path

from flask import current_app
from marshmallow import ValidationError
from PIL import Image
from sqlalchemy import select
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import NotFound

from app import db
from app.ia.fiabilite.empreintes import distance_hamming, empreintes_image
from app.models import ActionHistorique, Annonce, AnnoncePhoto, StatutAnnonce
from app.services.annonce_service import obtenir_annonce
from app.services.historique_service import enregistrer_action

EXTENSIONS_AUTORISEES = ("jpg", "jpeg", "png", "webp")
EXTENSION_PAR_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_PHOTOS_PAR_ANNONCE = 10
PREFIXE_URL = "/uploads/"


def _dossier_uploads() -> Path:
    """Renvoie le dossier des uploads, créé au besoin.

    Returns:
        Path: Dossier ``UPLOAD_FOLDER`` de la configuration.
    """
    dossier = Path(current_app.config["UPLOAD_FOLDER"])
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def _extension_declaree(nom_fichier: str) -> str:
    """Extrait l'extension (en minuscules) du nom envoyé par le client.

    Args:
        nom_fichier: Nom d'origine du fichier.

    Returns:
        str: Extension sans le point, ou chaîne vide.
    """
    return nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""


def _extension_reelle(fichier: FileStorage) -> str | None:
    """Vérifie avec Pillow que le fichier est réellement une image autorisée.

    Le contenu est analysé, pas le nom : un ``.exe`` renommé en ``.jpg`` est refusé.
    Les images démesurées (« bombes de décompression ») sont aussi refusées.

    Args:
        fichier: Fichier reçu.

    Returns:
        str | None: Extension correspondant au format réel (``jpg``, ``png``, ``webp``),
        ou ``None`` si le fichier n'est pas une image autorisée.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(fichier.stream) as image:
                format_reel = image.format
                image.verify()
    except Exception:  # toute erreur de décodage signifie que le fichier est refusé
        return None
    finally:
        fichier.stream.seek(0)
    return EXTENSION_PAR_FORMAT.get(format_reel)


def controler_image(fichier: FileStorage) -> tuple[str | None, str | None]:
    """Contrôle un fichier image : extension déclarée puis format réel (Pillow).

    Utilisé pour les photos d'annonces et la photo de profil des utilisateurs.

    Args:
        fichier: Fichier reçu.

    Returns:
        tuple[str | None, str | None]: ``(extension réelle, None)`` si le fichier est accepté,
        sinon ``(None, message d'erreur)``.
    """
    if _extension_declaree(fichier.filename) not in EXTENSIONS_AUTORISEES:
        return None, f"{fichier.filename} : format non autorisé (jpg, jpeg, png, webp)."
    if (extension := _extension_reelle(fichier)) is None:
        return None, f"{fichier.filename} : le fichier n'est pas une image valide (jpg, jpeg, png, webp)."
    return extension, None


def enregistrer_fichier(fichier: FileStorage, extension: str) -> tuple[Path, str]:
    """Enregistre un fichier déjà contrôlé sous un nom UUID (le nom d'origine n'entre jamais dans le chemin).

    Args:
        fichier: Fichier contrôlé par ``controler_image``.
        extension: Extension du format réel.

    Returns:
        tuple[Path, str]: Chemin sur le disque et URL publique (``/uploads/<uuid>.<ext>``).
    """
    nom = f"{uuid.uuid4().hex}.{extension}"
    chemin = _dossier_uploads() / nom
    fichier.save(chemin)
    return chemin, PREFIXE_URL + nom


def ajouter_photos(annonce_id: int, fichiers: list[FileStorage]) -> list[AnnoncePhoto]:
    """Valide puis enregistre des photos pour une annonce (tout ou rien).

    Chaque fichier est renommé avec un UUID et l'extension de son format réel :
    le nom d'origine n'entre jamais dans le chemin (pas de traversée de répertoire).

    Args:
        annonce_id: Identifiant de l'annonce.
        fichiers: Fichiers du champ ``photos`` de la requête multipart.

    Returns:
        list[AnnoncePhoto]: Photos créées, numérotées après la dernière photo existante.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
        marshmallow.ValidationError: Si aucun fichier, trop de photos ou un fichier invalide.
    """
    annonce = obtenir_annonce(annonce_id)
    fichiers = [fichier for fichier in fichiers if fichier.filename]
    if not fichiers:
        raise ValidationError({"photos": ["Au moins une photo est requise."]})

    deja_presentes = len(annonce.photos)
    if deja_presentes + len(fichiers) > MAX_PHOTOS_PAR_ANNONCE:
        raise ValidationError({"photos": [
            f"Maximum {MAX_PHOTOS_PAR_ANNONCE} photos par annonce ({deja_presentes} déjà présentes)."
        ]})

    erreurs: list[str] = []
    valides: list[tuple[FileStorage, str]] = []
    for fichier in fichiers:
        extension, erreur = controler_image(fichier)
        if erreur:
            erreurs.append(erreur)
        else:
            valides.append((fichier, extension))
    if erreurs:
        raise ValidationError({"photos": erreurs})

    ordre = max((photo.ordre for photo in annonce.photos), default=0)
    nouvelles: list[AnnoncePhoto] = []
    chemins: list[Path] = []
    try:
        for fichier, extension in valides:
            chemin, url = enregistrer_fichier(fichier, extension)
            chemins.append(chemin)
            ordre += 1
            sha256, phash = empreintes_image(chemin.read_bytes())
            photo = AnnoncePhoto(annonce_id=annonce.id, url=url, ordre=ordre, sha256=sha256, phash=phash)
            db.session.add(photo)
            nouvelles.append(photo)
        db.session.flush()  # attribue les identifiants des photos, repris dans l'historique
        if annonce.statut in (StatutAnnonce.PUBLIEE, StatutAnnonce.LOUEE, StatutAnnonce.VENDUE):
            photos_publiques = db.session.scalars(
                select(AnnoncePhoto)
                .join(Annonce, AnnoncePhoto.annonce_id == Annonce.id)
                .where(
                    AnnoncePhoto.annonce_id != annonce.id,
                    Annonce.statut.in_((StatutAnnonce.PUBLIEE, StatutAnnonce.LOUEE, StatutAnnonce.VENDUE)),
                )
            ).all()
            for photo in nouvelles:
                identique = next((
                    autre for autre in photos_publiques
                    if (
                        photo.sha256 and autre.sha256 and photo.sha256 == autre.sha256
                    ) or (
                        photo.phash and autre.phash
                        and distance_hamming(photo.phash, autre.phash) <= 6
                    )
                ), None)
                if identique is not None:
                    raise ValidationError({
                        "photos": [
                            "Cette photo est déjà utilisée dans une autre annonce publique. "
                            "Remplacez-la par votre propre photo."
                        ]
                    })
        enregistrer_action(annonce, ActionHistorique.AJOUT_PHOTOS, {
            "nombre": len(nouvelles),
            "photo_ids": [photo.id for photo in nouvelles],
        })
        db.session.commit()
    except Exception:
        db.session.rollback()
        for chemin in chemins:
            chemin.unlink(missing_ok=True)
        raise
    return nouvelles


def supprimer_photo(annonce_id: int, photo_id: int) -> None:
    """Supprime une photo de la base puis son fichier sur le disque.

    Args:
        annonce_id: Identifiant de l'annonce.
        photo_id: Identifiant de la photo.

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas ou si la photo
            n'appartient pas à cette annonce.
    """
    annonce = obtenir_annonce(annonce_id)
    photo = db.session.get(AnnoncePhoto, photo_id)
    if photo is None or photo.annonce_id != annonce_id:
        raise NotFound(f"Photo {photo_id} introuvable pour l'annonce {annonce_id}")
    url = photo.url
    position = [p.id for p in annonce.photos].index(photo.id) + 1  # rang affiché (1 = photo principale)
    enregistrer_action(annonce, ActionHistorique.SUPPRESSION_PHOTO, {"photo_id": photo.id, "position": position})
    db.session.delete(photo)
    db.session.commit()
    supprimer_fichiers([url])


def reordonner_photos(annonce_id: int, ids_photos: list[int]) -> list[AnnoncePhoto]:
    """Réordonne les photos d'une annonce selon la liste d'identifiants fournie.

    Args:
        annonce_id: Identifiant de l'annonce.
        ids_photos: Tous les identifiants des photos de l'annonce, dans le nouvel ordre.

    Returns:
        list[AnnoncePhoto]: Photos dans le nouvel ordre (``ordre`` = 1, 2, 3…).

    Raises:
        werkzeug.exceptions.NotFound: Si l'annonce n'existe pas.
        marshmallow.ValidationError: Si la liste contient des doublons ou ne correspond
            pas exactement aux photos de l'annonce.
    """
    annonce = obtenir_annonce(annonce_id)
    photos = {photo.id: photo for photo in annonce.photos}
    if len(ids_photos) != len(set(ids_photos)):
        raise ValidationError({"ordre": ["La liste contient des identifiants en double."]})
    if set(ids_photos) != set(photos):
        raise ValidationError({"ordre": [
            f"La liste doit contenir exactement les photos de l'annonce : {sorted(photos)}."
        ]})
    ordre_avant = [photo.id for photo in annonce.photos]  # relation triée par ``ordre``
    for position, photo_id in enumerate(ids_photos, start=1):
        photos[photo_id].ordre = position
    if ordre_avant != ids_photos:
        enregistrer_action(annonce, ActionHistorique.REORDONNANCEMENT_PHOTOS, {
            "avant": ordre_avant,
            "apres": ids_photos,
        })
    db.session.commit()
    return [photos[photo_id] for photo_id in ids_photos]


def supprimer_fichiers(urls: Iterable[str]) -> None:
    """Supprime du disque les fichiers correspondant à des URL ``/uploads/<nom>``.

    Seul le nom final de l'URL est utilisé, à l'intérieur de ``UPLOAD_FOLDER``.
    Un fichier déjà absent est ignoré.

    Args:
        urls: URL des photos (champ ``AnnoncePhoto.url``).
    """
    dossier = Path(current_app.config["UPLOAD_FOLDER"])
    for url in urls:
        if url.startswith(PREFIXE_URL):
            (dossier / Path(url).name).unlink(missing_ok=True)
