"""Accès à l'historique d'absence et persistance du prédicteur local."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from typing import Any

import joblib
from flask import current_app
from sqlalchemy import func, select

from app import db
from app.models import StatutVisite, TypeVisite, Visite
from app.services.planification_ml import (
    SEUIL_MIN_HISTORIQUE,
    PredicteurAbsence,
    carte_chaleur,
)

FICHIER_PREDICTEUR = "absence_visites.joblib"


def lignes_historique_visites(proprietaire_id: int | None = None) -> list[tuple[datetime, datetime, int, bool, int, bool]]:
    """Charge les visites terminées et calcule les absences antérieures par client.

    Args:
        proprietaire_id: Filtre facultatif pour les agrégats du tableau de bord.

    Returns:
        list[tuple[datetime, datetime, int, bool, int, bool]]: Lignes prêtes pour le modèle.
    """
    requete = select(Visite).where(
        Visite.statut.in_([StatutVisite.EFFECTUEE, StatutVisite.ABSENT])
    )
    if proprietaire_id is not None:
        requete = requete.where(Visite.proprietaire_id == proprietaire_id)
    visites = db.session.scalars(
        requete.order_by(Visite.date_visite, Visite.heure_debut, Visite.id)
    ).all()

    absences_client: dict[int, int] = defaultdict(int)
    lignes = []
    for visite in visites:
        debut = datetime.combine(visite.date_visite, time.fromisoformat(visite.heure_debut))
        demande = visite.date_demande
        if demande.tzinfo is not None:
            demande = demande.replace(tzinfo=None)
        absent = visite.statut == StatutVisite.ABSENT
        lignes.append((
            debut,
            demande,
            visite.nb_personnes,
            visite.type_visite == TypeVisite.VIRTUELLE,
            absences_client[visite.client_id],
            absent,
        ))
        if absent:
            absences_client[visite.client_id] += 1
    return lignes


def donnees_carte_chaleur(proprietaire_id: int) -> list[dict[str, Any]]:
    """Prépare les taux et volumes d'absence pour le tableau de bord propriétaire.

    Args:
        proprietaire_id: Identifiant du propriétaire connecté.

    Returns:
        list[dict[str, Any]]: Une entrée par jour et heure observés.
    """
    lignes = lignes_historique_visites(proprietaire_id)
    taux = carte_chaleur(lignes)
    volumes: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"total": 0, "absents": 0})
    for ligne in lignes:
        cle = (ligne[0].weekday(), ligne[0].hour)
        volumes[cle]["total"] += 1
        volumes[cle]["absents"] += int(ligne[5])
    return [
        {"jour": jour, "heure": heure, **volumes[(jour, heure)], "taux": taux[(jour, heure)]}
        for jour, heure in sorted(taux)
    ]


def chemin_predicteur() -> Path:
    """Retourne le chemin du modèle persistant ignoré par Git."""
    return Path(current_app.config["MODELES_FOLDER"]) / "planification-visites" / FICHIER_PREDICTEUR


def entrainer_et_sauver() -> tuple[PredicteurAbsence, int]:
    """Réentraîne le modèle sur toutes les visites historiques et le persiste localement.

    Returns:
        tuple[PredicteurAbsence, int]: Modèle produit et nombre de visites utilisées.
    """
    lignes = lignes_historique_visites()
    predicteur = PredicteurAbsence().entrainer(lignes)
    destination = chemin_predicteur()
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(predicteur, destination)
    return predicteur, len(lignes)


def charger_ou_entrainer() -> PredicteurAbsence:
    """Charge le dernier modèle ou entraîne une première version depuis l'historique courant."""
    nombre_visites = db.session.scalar(
        select(func.count()).select_from(Visite).where(
            Visite.statut.in_([StatutVisite.EFFECTUEE, StatutVisite.ABSENT])
        )
    ) or 0
    if nombre_visites < SEUIL_MIN_HISTORIQUE:
        return PredicteurAbsence().entrainer([])

    chemin = chemin_predicteur()
    if chemin.is_file():
        try:
            predicteur = joblib.load(chemin)
            if isinstance(predicteur, PredicteurAbsence):
                return predicteur
        except (OSError, EOFError, ValueError, AttributeError, ImportError):
            current_app.logger.warning("Le modèle de prédiction des absences est illisible; réentraînement local.")
    predicteur, _ = entrainer_et_sauver()
    return predicteur
