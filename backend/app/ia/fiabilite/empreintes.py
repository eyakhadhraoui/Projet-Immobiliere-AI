"""Empreintes privées des photos d'annonces."""

from __future__ import annotations

import hashlib
from io import BytesIO

import imagehash
from PIL import Image, UnidentifiedImageError


def empreintes_image(contenu: bytes) -> tuple[str, str | None]:
    """Calcule SHA-256 et pHash 64 bits à partir des octets d'une image.

    Args:
        contenu: Octets du fichier image.

    Returns:
        tuple[str, str | None]: SHA-256 et pHash hexadécimal, absent si l'image est illisible.
    """
    sha256 = hashlib.sha256(contenu).hexdigest()
    try:
        with Image.open(BytesIO(contenu)) as image:
            phash = str(imagehash.phash(image.convert("RGB")))
    except (OSError, UnidentifiedImageError, ValueError):
        phash = None
    return sha256, phash


def distance_hamming(gauche: str, droite: str) -> int:
    """Compte les bits différents de deux pHash hexadécimaux de 64 bits."""
    if len(gauche) != 16 or len(droite) != 16:
        raise ValueError("Les pHash doivent contenir 16 caractères hexadécimaux.")
    try:
        return (int(gauche, 16) ^ int(droite, 16)).bit_count()
    except ValueError as erreur:
        raise ValueError("pHash hexadécimal invalide.") from erreur
