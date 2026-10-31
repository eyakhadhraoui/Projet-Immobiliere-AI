"""Chargement et validation du jeu annoté fictif de contrôle de fiabilité."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ENSEMBLES = {"entrainement", "validation", "test"}


class JeuFiabiliteInvalide(ValueError):
    """Le jeu de fiabilité ne respecte pas son schéma ou son split."""


def charger_jeu(chemin: str | Path) -> dict[str, Any]:
    """Charge le JSON du jeu puis vérifie les champs, groupes et ensembles.

    Args:
        chemin: Chemin du fichier `jeu_annote.json`.

    Returns:
        dict[str, Any]: Jeu validé.
    """
    with Path(chemin).open(encoding="utf-8") as fichier:
        jeu = json.load(fichier)
    annonces = jeu.get("annonces")
    if not isinstance(annonces, list) or not annonces:
        raise JeuFiabiliteInvalide("Le jeu ne contient aucune annonce.")
    groupes: dict[str, set[str]] = {}
    ids: set[str] = set()
    for annonce in annonces:
        identifiant, groupe, ensemble = annonce.get("id"), annonce.get("groupe"), annonce.get("ensemble")
        if not all(isinstance(x, str) and x for x in (identifiant, groupe)) or ensemble not in ENSEMBLES:
            raise JeuFiabiliteInvalide("Identifiant, groupe ou ensemble invalide.")
        if identifiant in ids:
            raise JeuFiabiliteInvalide("Identifiant d'annonce dupliqué.")
        ids.add(identifiant)
        groupes.setdefault(groupe, set()).add(ensemble)
        if not isinstance(annonce.get("description"), str) or not annonce["description"].strip():
            raise JeuFiabiliteInvalide(f"Description vide pour {identifiant}.")
    fuites = sorted(groupe for groupe, ensembles in groupes.items() if len(ensembles) != 1)
    if fuites:
        raise JeuFiabiliteInvalide(f"Fuite inter-ensembles pour les groupes: {', '.join(fuites)}.")
    comptes = Counter(annonce["ensemble"] for annonce in annonces)
    if not all(comptes.get(nom, 0) > 0 for nom in ENSEMBLES):
        raise JeuFiabiliteInvalide("Train, validation et test doivent être non vides.")
    return jeu
