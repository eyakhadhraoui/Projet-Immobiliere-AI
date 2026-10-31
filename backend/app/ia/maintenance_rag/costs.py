"""Estimations de coût et de durée par fiche, lues dans data/couts.json."""
import json
import math
from pathlib import Path

FULL_DAY_HOURS = 8


def _hours_label(hours: float) -> str:
    minutes = round(hours * 60)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h" if m == 0 else f"{h} h {m:02d}"


def duration_label(min_hours: float, max_hours: float) -> str:
    """Au-delà d'une journée de travail, la durée est exprimée en jours (1 jour = 8 h)."""
    if max_hours > FULL_DAY_HOURS:
        low = max(1, math.ceil(min_hours / FULL_DAY_HOURS))
        high = math.ceil(max_hours / FULL_DAY_HOURS)
        return f"{low} jour{'s' if low > 1 else ''}" if low == high else f"{low} à {high} jours"
    return f"{_hours_label(min_hours)} à {_hours_label(max_hours)}"


class CostTable:
    def __init__(self, path: Path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._meta = data["meta"]
        self._fiches = data["fiches"]

    def estimate(self, fiche_id: str | None) -> dict | None:
        """Estimation indicative pour une fiche, ou None si l'identifiant est inconnu ou absent."""
        entry = self._fiches.get(fiche_id) if fiche_id else None
        if entry is None:
            return None
        return {
            "cout_min": entry["cout_min"],
            "cout_max": entry["cout_max"],
            "devise": self._meta["currency"],
            "duree_min_heures": entry["duree_min_heures"],
            "duree_max_heures": entry["duree_max_heures"],
            "duree_libelle": duration_label(entry["duree_min_heures"], entry["duree_max_heures"]),
            "technicien": entry["technicien"],
            "inclus": entry["inclus"],
            "hypotheses": entry["hypotheses"],
            "facteurs_de_variation": entry["facteurs_de_variation"],
            "fiabilite": entry["fiabilite"],
            "avertissement": self._meta["disclaimer"],
        }