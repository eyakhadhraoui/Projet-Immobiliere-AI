"""Import du jeu de données « Property Prices in Tunisia » (Kaggle) pour l'estimation du prix (IA-ANNONCE-PPT-001).

Le fichier CSV contient des annonces immobilières tunisiennes réelles (prix AFFICHÉS, pas prix de vente conclus),
en vente et en location. Colonnes : category, room_count, bathroom_count, size, type, price, city (gouvernorat),
region, log_price (= log10(price), non utilisé : on recalcule nos propres variables).

Ce module ne fait que LIRE et ADAPTER le fichier au format des annonces de l'application ; le contrôle qualité
commun (valeurs manquantes, prix au m² aberrants, doublons) reste fait par ``estimation_prix.preparer_donnees``.

Choix d'adaptation (à dire à l'oral) :
- seules les catégories « Appartements » et « Maisons et Villas » correspondent aux biens de l'application ;
  terrains, bureaux, commerces, colocations et locations de vacances sont écartés ;
- « Maisons et Villas » devient le type « maison » : le fichier ne distingue pas une maison d'une villa ;
- ville = région quand elle est précisée, sinon le gouvernorat (région « Autres villes ») ;
- ``size`` et ``room_count`` valent -1 quand ils sont inconnus : annonce écartée ;
- un loyer sous ``LOYER_MIN`` TND est très probablement un prix à la nuit (locations saisonnières mal classées) ;
- le fichier ne contient ni équipements, ni meublé : ils sont mis à « absent » (voir ``ajustements_demo``).
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

NOM_SOURCE = "Property Prices in Tunisia (Kaggle)"
COLONNES = ("category", "room_count", "bathroom_count", "size", "type", "price", "city", "region")
CATEGORIES = {"Appartements": "appartement", "Maisons et Villas": "maison"}
TRANSACTIONS = {"À Louer": "location", "À Vendre": "vente"}
REGION_INCONNUE = "Autres villes"
LOYER_MIN = 150  # TND/mois : en dessous, prix à la nuit d'une location saisonnière (observé dans le fichier)
REGLES = (
    "catégories gardées : Appartements (type appartement), Maisons et Villas (type maison)",
    "ville = région, ou gouvernorat si la région vaut « Autres villes »",
    "surface ou nombre de pièces inconnus (-1) ou nuls : annonce écartée",
    "nombre de salles de bain inconnu ou négatif : annonce écartée",
    f"location à moins de {LOYER_MIN} TND : écartée (probablement un prix à la nuit)",
    "équipements et meublé : absents du fichier, mis à « non »",
)


def _texte(valeur: Any) -> str:
    """Texte nettoyé (NFC, espaces superflus retirés) ; chaîne vide si la valeur est absente."""
    if pd.isna(valeur):
        return ""
    return " ".join(unicodedata.normalize("NFC", str(valeur)).split())


def _positif(valeur: Any) -> float | None:
    """Nombre strictement positif, sinon None (-1 = inconnu dans le fichier)."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre > 0 and not pd.isna(nombre) else None


def empreinte(fichier: Path) -> str:
    """Empreinte SHA-256 du fichier (permet de savoir exactement quelles données ont servi)."""
    return hashlib.sha256(fichier.read_bytes()).hexdigest()


def lire(fichier: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Lit le CSV et le convertit en annonces au format de l'application.

    Args:
        fichier: Chemin du CSV « Property Prices in Tunisia ».

    Returns:
        tuple: (annonces, rapport d'import avec les effectifs écartés par règle).

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si une colonne attendue manque.
    """
    if not fichier.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {fichier}")
    donnees = pd.read_csv(fichier, encoding="utf-8")
    manquantes = [c for c in COLONNES if c not in donnees.columns]
    if manquantes:
        raise ValueError(f"Colonnes absentes du fichier : {', '.join(manquantes)}")

    ecartees: Counter[str] = Counter()
    annonces: list[dict[str, Any]] = []
    for position, ligne in enumerate(donnees.itertuples(index=False)):
        categorie = _texte(ligne.category)
        transaction = TRANSACTIONS.get(_texte(ligne.type))
        if categorie not in CATEGORIES or transaction is None:
            ecartees["categorie_hors_perimetre"] += 1
            continue
        surface, pieces = _positif(ligne.size), _positif(ligne.room_count)
        if surface is None or pieces is None:
            ecartees["surface_ou_pieces_inconnues"] += 1
            continue
        try:
            salles_de_bain = float(ligne.bathroom_count)
        except (TypeError, ValueError):
            salles_de_bain = float("nan")
        if pd.isna(salles_de_bain) or salles_de_bain < 0:
            ecartees["salles_de_bain_inconnues"] += 1
            continue
        prix = _positif(ligne.price)
        if prix is None:
            ecartees["prix_absent"] += 1
            continue
        if transaction == "location" and prix < LOYER_MIN:
            ecartees["loyer_a_la_nuit"] += 1
            continue
        gouvernorat, region = _texte(ligne.city), _texte(ligne.region)
        annonces.append({
            "id": None,
            "titre": f"PPT ligne {position + 2}",  # numéro de ligne du CSV (la ligne 1 est l'en-tête)
            "type_bien": CATEGORIES[categorie],
            "transaction": transaction,
            "ville": region if region and region != REGION_INCONNUE else gouvernorat,
            "gouvernorat": gouvernorat,
            "surface": surface,
            "nb_pieces": int(pieces),
            "nb_sdb": int(salles_de_bain),
            "meuble": False,
            "caracteristiques": [],
            "prix": prix,
        })
    rapport = {
        "nom": NOM_SOURCE,
        "fichier": fichier.name,
        "sha256": empreinte(fichier),
        "nb_lignes": len(donnees),
        "nb_annonces_importees": len(annonces),
        "ecartees": dict(ecartees),
        "regles": list(REGLES),
        "par_transaction": dict(Counter(a["transaction"] for a in annonces)),
        "par_type": dict(Counter(a["type_bien"] for a in annonces)),
    }
    return annonces, rapport
