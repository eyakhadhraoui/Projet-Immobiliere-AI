"""Prédiction locale des absences aux visites et ajustement des créneaux."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression

SEUIL_MIN_HISTORIQUE = 50


def _sans_fuseau(moment: datetime) -> datetime:
    """Retire le fuseau sans changer l'heure murale pour comparer les dates métier."""
    return moment.replace(tzinfo=None) if moment.tzinfo else moment


def caracteristiques(
    debut: datetime,
    demande: datetime,
    nb_personnes: int,
    virtuelle: bool,
    absences_passees: int,
) -> list[int]:
    """Convertit les caractéristiques connues d'une visite en valeurs numériques.

    Args:
        debut: Date et heure prévues de la visite.
        demande: Date et heure de création de la demande.
        nb_personnes: Nombre de visiteurs déclaré.
        virtuelle: Indique si la visite est virtuelle.
        absences_passees: Nombre d'absences antérieures du client.

    Returns:
        list[int]: Variables attendues par le modèle logistique.
    """
    delai = max(0, (_sans_fuseau(debut) - _sans_fuseau(demande)).days)
    return [
        debut.hour,
        int(debut.weekday() >= 5),
        int(debut.weekday() == 4),
        delai,
        max(1, nb_personnes),
        int(virtuelle),
        max(0, absences_passees),
    ]


class PredicteurAbsence:
    """Classifieur local qui estime la probabilité d'absence à une visite."""

    def __init__(self) -> None:
        """Initialise une régression logistique non entraînée."""
        self.modele = LogisticRegression(max_iter=1000, random_state=42)
        self.pret = False
        self.nb_visites = 0

    def entrainer(self, lignes: Sequence[tuple[datetime, datetime, int, bool, int, bool]]) -> PredicteurAbsence:
        """Entraîne le modèle si l'historique dépasse le minimum et contient deux classes.

        Args:
            lignes: Tuples (début, demande, personnes, virtuelle, absences passées, absent).

        Returns:
            PredicteurAbsence: Cette instance entraînée ou laissée inactive.
        """
        self.nb_visites = len(lignes)
        if len(lignes) < SEUIL_MIN_HISTORIQUE or len({ligne[5] for ligne in lignes}) < 2:
            self.pret = False
            return self
        x = np.asarray([caracteristiques(*ligne[:5]) for ligne in lignes], dtype=float)
        y = np.asarray([int(ligne[5]) for ligne in lignes], dtype=int)
        self.modele.fit(x, y)
        self.pret = True
        return self

    def proba_absence(
        self,
        debut: datetime,
        demande: datetime,
        nb_personnes: int = 1,
        virtuelle: bool = False,
        absences_passees: int = 0,
    ) -> float:
        """Renvoie la probabilité prédite d'absence, ou un niveau neutre si inactif.

        Args:
            debut: Date et heure proposées.
            demande: Date et heure de la demande.
            nb_personnes: Nombre de visiteurs prévu.
            virtuelle: Indique si le rendez-vous est virtuel.
            absences_passees: Absences antérieures du client.

        Returns:
            float: Probabilité comprise entre 0 et 1.
        """
        if not self.pret:
            return 0.10
        x = np.asarray([caracteristiques(debut, demande, nb_personnes, virtuelle, absences_passees)])
        return float(self.modele.predict_proba(x)[0, 1])


def ajuster_score(score_regles: int, proba: float) -> int:
    """Retire jusqu'à 40 points aux créneaux à risque élevé.

    Args:
        score_regles: Score obtenu par les règles de disponibilité existantes.
        proba: Probabilité d'absence comprise entre 0 et 1.

    Returns:
        int: Score ajusté borné entre 0 et 100.
    """
    return int(max(0, min(100, score_regles - 40 * max(0.0, min(1.0, proba)))))


def carte_chaleur(lignes: Sequence[tuple[datetime, datetime, int, bool, int, bool]]) -> dict[tuple[int, int], float]:
    """Calcule le taux d'absence pour chaque jour de semaine et heure.

    Args:
        lignes: Historique labellisé dans le même format que l'entraînement.

    Returns:
        dict[tuple[int, int], float]: Taux arrondi par (jour ISO, heure).
    """
    totaux: dict[tuple[int, int], int] = {}
    absences: dict[tuple[int, int], int] = {}
    for ligne in lignes:
        debut, absent = ligne[0], bool(ligne[5])
        cle = (debut.weekday(), debut.hour)
        totaux[cle] = totaux.get(cle, 0) + 1
        absences[cle] = absences.get(cle, 0) + int(absent)
    return {cle: round(absences[cle] / nombre, 2) for cle, nombre in totaux.items()}
