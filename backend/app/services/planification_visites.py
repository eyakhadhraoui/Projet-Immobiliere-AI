"""Proposition et validation des créneaux de visite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.models import Annonce, DisponibiliteVisite, StatutVisite, Visite
from app.services.planification_ml import PredicteurAbsence, ajuster_score

DUREE_VISITE_MIN = 30
TAMPON_MIN = 15
JOURS_A_PROPOSER = 14
NB_PROPOSITIONS = 3


@dataclass(frozen=True)
class Proposition:
    """Créneau proposé avec son score et ses raisons."""

    debut: datetime
    fin: datetime
    score: int
    raisons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise la proposition pour l'API."""
        return {
            "debut": self.debut.isoformat(),
            "fin": self.fin.isoformat(),
            "date": self.debut.date().isoformat(),
            "heure_debut": self.debut.strftime("%H:%M"),
            "heure_fin": self.fin.strftime("%H:%M"),
            "score": self.score,
            "etiquette": "Recommandé" if self.score >= 80 else "Disponible",
            "raisons": self.raisons,
        }


def _distance_km(annonce_a: Annonce, annonce_b: Annonce) -> float:
    """Calcule la distance à vol d'oiseau entre deux annonces."""
    if annonce_a.latitude is None or annonce_a.longitude is None:
        return 0.0
    if annonce_b.latitude is None or annonce_b.longitude is None:
        return 0.0
    lat_a, lon_a, lat_b, lon_b = map(
        radians,
        (annonce_a.latitude, annonce_a.longitude, annonce_b.latitude, annonce_b.longitude),
    )
    haversine = sin((lat_b - lat_a) / 2) ** 2
    haversine += cos(lat_a) * cos(lat_b) * sin((lon_b - lon_a) / 2) ** 2
    return 6371 * 2 * asin(sqrt(haversine))


def _trajet_min(annonce_a: Annonce, annonce_b: Annonce) -> int:
    """Estime le trajet entre deux annonces."""
    if annonce_a.id == annonce_b.id:
        return 0
    return int(_distance_km(annonce_a, annonce_b) / 30 * 60) + 5


def est_libre(debut: datetime, fin: datetime, annonce: Annonce, visites: list[Visite]) -> bool:
    """Vérifie l'absence de chevauchement avec tampon et trajet."""
    for visite in visites:
        autre_annonce = visite.annonce
        marge = timedelta(minutes=max(TAMPON_MIN, _trajet_min(autre_annonce, annonce)))
        visite_debut = datetime.combine(visite.date_visite, time.fromisoformat(visite.heure_debut))
        visite_fin = datetime.combine(visite.date_visite, time.fromisoformat(visite.heure_fin))
        if debut < visite_fin + marge and fin > visite_debut - marge:
            return False
    return True


def _disponible(
    jour: date,
    debut: datetime,
    fin: datetime,
    disponibilites: list[DisponibiliteVisite],
    annonce: Annonce,
    visites: list[Visite],
) -> bool:
    """Vérifie qu'un créneau respecte une disponibilité et reste libre."""
    jour_db = jour.weekday() + 1
    for disponibilite in disponibilites:
        if not disponibilite.actif or disponibilite.jour_semaine != jour_db:
            continue
        debut_dispo = time.fromisoformat(disponibilite.heure_debut)
        fin_dispo = time.fromisoformat(disponibilite.heure_fin)
        if debut.time() >= debut_dispo and fin.time() <= fin_dispo:
            return est_libre(debut, fin, annonce, visites)
    return False


def _score(debut: datetime, maintenant: datetime, visites: list[Visite]) -> tuple[int, list[str]]:
    """Calcule un score stable pour classer les créneaux."""
    score = 70
    raisons = ["Créneau libre dans les disponibilités de l'annonce"]
    if debut.hour < 12:
        score += 15
        raisons.append("Horaire du matin")
    elif debut.hour < 17:
        score += 10
        raisons.append("Horaire de l'après-midi")
    if not visites:
        score += 10
        raisons.append("Aucune autre visite confirmée ce jour-là")
    delai = (debut.date() - maintenant.date()).days
    score += max(0, min(5, 5 - delai))
    return min(100, score), raisons


def proposer_creneaux(
    annonce: Annonce,
    disponibilites: list[DisponibiliteVisite],
    visites: list[Visite],
    maintenant: datetime | None = None,
    nb: int = NB_PROPOSITIONS,
    predicteur: PredicteurAbsence | None = None,
    absences_passees: int = 0,
) -> list[Proposition]:
    """Retourne les meilleurs créneaux libres des quatorze prochains jours.

    Args:
        annonce: Bien concerné par la visite.
        disponibilites: Plages hebdomadaires renseignées par le propriétaire.
        visites: Visites qui occupent des créneaux.
        maintenant: Date de référence, ou heure courante.
        nb: Nombre de créneaux retournés.
        predicteur: Modèle entraîné, sinon les scores de règles restent inchangés.
        absences_passees: Absences antérieures du visiteur connecté.

    Returns:
        list[Proposition]: Meilleurs créneaux triés par score décroissant.
    """
    maintenant = maintenant or datetime.now()
    resultats: list[Proposition] = []
    for decalage in range(1, JOURS_A_PROPOSER + 1):
        jour = (maintenant + timedelta(days=decalage)).date()
        visites_jour = [visite for visite in visites if visite.date_visite == jour]
        for disponibilite in disponibilites:
            if not disponibilite.actif or disponibilite.jour_semaine != jour.weekday() + 1:
                continue
            debut = datetime.combine(jour, time.fromisoformat(disponibilite.heure_debut))
            fin_disponible = datetime.combine(jour, time.fromisoformat(disponibilite.heure_fin))
            while debut + timedelta(minutes=DUREE_VISITE_MIN) <= fin_disponible:
                fin = debut + timedelta(minutes=DUREE_VISITE_MIN)
                if _disponible(jour, debut, fin, disponibilites, annonce, visites_jour):
                    score, raisons = _score(debut, maintenant, visites_jour)
                    if predicteur is not None and predicteur.pret:
                        risque = predicteur.proba_absence(
                            debut, maintenant, absences_passees=absences_passees
                        )
                        score_ajuste = ajuster_score(score, risque)
                        if score_ajuste < score:
                            raisons = [*raisons, "Score ajusté selon le risque d'absence historique"]
                        score = score_ajuste
                    resultats.append(Proposition(debut, fin, score, raisons))
                debut = fin
    resultats.sort(key=lambda proposition: (-proposition.score, proposition.debut))
    return resultats[:nb]


def creneau_autorise(
    annonce: Annonce,
    date_visite: date,
    heure_debut: str,
    heure_fin: str,
    disponibilites: list[DisponibiliteVisite],
    visites: list[Visite],
) -> bool:
    """Vérifie côté serveur le créneau choisi par le visiteur."""
    debut = datetime.combine(date_visite, time.fromisoformat(heure_debut))
    fin = datetime.combine(date_visite, time.fromisoformat(heure_fin))
    if fin <= debut or fin - debut != timedelta(minutes=DUREE_VISITE_MIN):
        return False
    return _disponible(date_visite, debut, fin, disponibilites, annonce, visites)


def statuts_bloquants() -> tuple[StatutVisite, ...]:
    """Renvoie les statuts qui occupent un créneau."""
    return (StatutVisite.EN_ATTENTE, StatutVisite.CONFIRMEE, StatutVisite.REPORTEE)
