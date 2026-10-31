"""Accès limité aux contrats de location utilisés par les dossiers litigieux."""

from __future__ import annotations

from typing import Any

from app import db
from app.models import LocationImmo


def location_pour_participant(location_id: int, utilisateur_id: int) -> LocationImmo | None:
    """Retourne une location uniquement si l'utilisateur est bailleur ou locataire.

    Args:
        location_id: Identifiant du contrat de location.
        utilisateur_id: Compte qui demande à rattacher un dossier.

    Returns:
        LocationImmo | None: Location autorisée, ou ``None`` si absente/non autorisée.
    """
    location = db.session.get(LocationImmo, location_id)
    if location is None or utilisateur_id not in {location.proprietaire_id, location.locataire_id}:
        return None
    return location


def contexte_litige_location(location: LocationImmo | None) -> dict[str, Any] | None:
    """Construit le contexte de bail utile au dossier sans exposer les données des parties.

    Args:
        location: Contrat de location rattaché au dossier, s'il existe.

    Returns:
        dict[str, Any] | None: Référence, annonce, dates et indicateur de contrat disponible.
    """
    if location is None:
        return None
    return {
        "id": location.id,
        "reference": location.reference,
        "annonce_id": location.annonce_id,
        "date_debut": location.date_debut.isoformat() if location.date_debut else None,
        "date_fin": location.date_fin.isoformat() if location.date_fin else None,
        "statut": location.statut.value if hasattr(location.statut, "value") else str(location.statut),
        "contrat_disponible": bool(location.contrat_pdf),
    }
