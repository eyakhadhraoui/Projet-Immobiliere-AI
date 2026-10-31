"""Repérage exploratoire d'annonces atypiques (sans étiquette de fraude).

Le score est une position relative dans la distribution des scores de validation, pas une
probabilité. Le seuil indique uniquement la part maximale d'annonces proposées à une revue.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, RobustScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

FICHIER_MODELE = "anomalies_annonces.joblib"
FICHIER_RAPPORT = "EVALUATION_ANOMALIES_ANNONCES.json"
MINIMUM = 100
TAUX_REVUE = 0.05
NUMERIQUES = ["log_prix_m2", "log_surface", "nb_pieces"]
CATEGORIQUES = ["transaction", "type_bien", "ville"]


class DonneesAnnoncesInvalides(ValueError):
    pass


def _normaliser(annonces: list[dict[str, Any]], *, exclure_prix_aberrants: bool = False) -> pd.DataFrame:
    lignes = []
    for a in annonces:
        try:
            prix, surface = float(a["prix"]), float(a["surface"])
            pieces = int(a["nb_pieces"])
            transaction, type_bien = str(a["transaction"]).strip().lower(), str(a["type_bien"]).strip().lower()
            ville = " ".join(str(a["ville"]).casefold().split())
        except (KeyError, TypeError, ValueError) as exc:
            raise DonneesAnnoncesInvalides("Une annonce ne contient pas les champs attendus.") from exc
        if not all(map(math.isfinite, (prix, surface))) or prix <= 0 or surface <= 0 or pieces < 0:
            raise DonneesAnnoncesInvalides("Prix, surface et nombre de pièces doivent être valides.")
        if transaction not in {"vente", "location"} or not ville or not type_bien:
            raise DonneesAnnoncesInvalides("Transaction, type de bien ou ville invalide.")
        prix_m2 = prix / surface
        # Bornes de qualité du pipeline immobilier existant; elles rejettent les incohérences grossières.
        if (transaction == "vente" and not 100 <= prix_m2 <= 20000) or (transaction == "location" and not 1 <= prix_m2 <= 200):
            if exclure_prix_aberrants:
                continue
            raise DonneesAnnoncesInvalides("Le prix par m² est hors des bornes de contrôle du projet.")
        lignes.append({"transaction": transaction, "type_bien": type_bien, "ville": ville,
                       "prix": prix, "surface": surface, "nb_pieces": pieces,
                       "log_prix_m2": math.log1p(prix_m2), "log_surface": math.log1p(surface)})
    if not lignes:
        raise DonneesAnnoncesInvalides("Aucune annonce exploitable.")
    return pd.DataFrame(lignes)


def _pipeline(graine: int, arbres: int, max_samples: int | str) -> Pipeline:
    prep = ColumnTransformer([
        ("num", RobustScaler(), NUMERIQUES),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=2), CATEGORIQUES),
    ])
    return Pipeline([("preparation", prep), ("modele", IsolationForest(
        n_estimators=arbres, max_samples=max_samples, contamination="auto", random_state=graine, n_jobs=-1
    ))])


def entrainer(annonces: list[dict[str, Any]], dossier: str | Path, graine: int = 42) -> dict[str, Any]:
    df = _normaliser(annonces, exclure_prix_aberrants=True)
    valides_avant_dedoublonnage = len(df)
    doublons = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    if len(df) < MINIMUM:
        raise DonneesAnnoncesInvalides(f"Il faut au moins {MINIMUM} annonces propres; {len(df)} disponibles.")
    # Séparer par empreinte de contenu pour empêcher les annonces identiques de fuir entre splits.
    empreintes = pd.util.hash_pandas_object(df, index=False).astype(str)
    groupes = empreintes.drop_duplicates().to_numpy()
    train_ids, reste_ids = train_test_split(groupes, test_size=0.4, random_state=graine)
    val_ids, test_ids = train_test_split(reste_ids, test_size=0.5, random_state=graine)
    train_mask, val_mask, test_mask = empreintes.isin(train_ids), empreintes.isin(val_ids), empreintes.isin(test_ids)
    train, val, test = df[train_mask], df[val_mask], df[test_mask]
    if min(len(train), len(val), len(test)) < 10:
        raise DonneesAnnoncesInvalides("Données insuffisantes après séparation sans doublons.")

    # Calibration sur validation seulement. Le paramètre n_estimators est retenu selon la stabilité
    # des rangs entre deux forêts à graines différentes; pas de labels, donc pas de score de classification.
    candidats = [100, 200]
    scores_val = []
    for arbres in candidats:
        modele = _pipeline(graine, arbres, min(256, len(train)))
        modele.fit(train[NUMERIQUES + CATEGORIQUES])
        scores_val.append(-modele.decision_function(val[NUMERIQUES + CATEGORIQUES]))
    correlations = [float(pd.Series(scores_val[0]).corr(pd.Series(scores_val[1]), method="spearman"))]
    retenu = candidats[int(correlations[0] < 0.98)]
    modele = _pipeline(graine, retenu, min(256, len(train)))
    modele.fit(train[NUMERIQUES + CATEGORIQUES])
    val_scores = -modele.decision_function(val[NUMERIQUES + CATEGORIQUES])
    seuil = float(np.quantile(val_scores, 1 - TAUX_REVUE))
    test_scores = -modele.decision_function(test[NUMERIQUES + CATEGORIQUES])

    # Référence explicite : extrêmes prix/m² selon transaction, seuils calculés sur train seulement.
    bornes = {}
    quantiles = {}
    frequences = {}
    for transaction, groupe in train.groupby("transaction"):
        ratio = groupe["prix"] / groupe["surface"]
        bornes[transaction] = [float(ratio.quantile(.01)), float(ratio.quantile(.99))]
    for colonne in NUMERIQUES:
        quantiles[colonne] = [float(train[colonne].quantile(.01)), float(train[colonne].quantile(.99))]
    for colonne in CATEGORIQUES:
        frequences[colonne] = (train[colonne].value_counts(normalize=True).to_dict())
    baseline = []
    for _, row in test.iterrows():
        low, high = bornes[row.transaction]
        baseline.append(not low <= row.prix / row.surface <= high)
    predicted = test_scores >= seuil
    rapport = {
        "nature": "non_supervise_sans_labels; anomalie statistique != fraude",
        "n_annonces_source_importees": len(annonces), "n_annonces_valides": len(df),
        "n_valides_avant_dedoublonnage": valides_avant_dedoublonnage,
        "n_doublons_exclus": doublons,
        "n_exclues_controle_qualite": len(annonces) - valides_avant_dedoublonnage,
        "n_train": len(train), "n_validation": len(val), "n_test": len(test),
        "doublons_identiques_inter_splits": 0,
        "modele": "IsolationForest", "parametres": {"n_estimators": retenu, "max_samples": min(256, len(train)),
                    "random_state": graine, "contamination": "auto"},
        "validation": {"stabilite_spearman_100_200": correlations[0], "quantile_seuil": 1-TAUX_REVUE,
                       "seuil_score_brut": seuil, "interpretation": "budget de revue, pas précision cible"},
        "test": {"alertes_modele": int(predicted.sum()), "taux_alertes_modele": float(predicted.mean()),
                 "alertes_regle_prix_m2": int(sum(baseline)), "taux_alertes_regle_prix_m2": float(np.mean(baseline)),
                 "accord_modele_regle": float(np.mean(predicted == np.asarray(baseline))),
                 "metriques_supervisees": None},
        "bornes_prix_m2_train": bornes,
        "quantiles_caracteristiques_train": quantiles,
        "limites": ["Le jeu de données contient des prix affichés, sans labels d'anomalie.",
                    "Les alertes sont à vérifier par une personne; elles ne caractérisent pas une fraude."],
    }
    artefact = {"pipeline": modele, "seuil": seuil, "scores_validation": np.sort(val_scores),
                "bornes": bornes, "quantiles": quantiles, "frequences": frequences, "rapport": rapport}
    dossier = Path(dossier); dossier.mkdir(parents=True, exist_ok=True)
    joblib.dump(artefact, dossier / FICHIER_MODELE)
    (dossier / FICHIER_RAPPORT).write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapport


def evaluer(annonces: list[dict[str, Any]], dossier: str | Path) -> dict[str, Any]:
    """Évalue le modèle sauvegardé sur les observations fournies (jeu indépendant à fournir)."""
    artefact = charger(dossier)
    df = _normaliser(annonces, exclure_prix_aberrants=True)
    scores = -artefact["pipeline"].decision_function(df[NUMERIQUES + CATEGORIQUES])
    pred = scores >= artefact["seuil"]
    resultat = {"n_test_source": len(annonces), "n_test": len(df),
                "n_exclues_controle_qualite": len(annonces) - len(df),
                "alertes": int(pred.sum()), "taux_alertes": float(pred.mean()),
                "metriques_supervisees": None, "interpretation": "aucun label: rappel/précision/F1 indisponibles"}
    return resultat


def charger(dossier: str | Path) -> dict[str, Any]:
    chemin = Path(dossier) / FICHIER_MODELE
    if not chemin.is_file():
        raise FileNotFoundError("Modèle d'anomalies non entraîné.")
    return joblib.load(chemin)


def analyser(annonce: dict[str, Any], dossier: str | Path) -> dict[str, Any]:
    """Retourne un score relatif, un seuil et des facteurs de règle interprétables."""
    df = _normaliser([annonce]); a = df.iloc[0]
    artefact = charger(dossier)
    score = float(-artefact["pipeline"].decision_function(df[NUMERIQUES + CATEGORIQUES])[0])
    reference = artefact["scores_validation"]
    percentile = float(np.searchsorted(reference, score, side="right") / len(reference))
    bornes = artefact["bornes"].get(a.transaction)
    ratio = a.prix / a.surface
    facteurs = []
    regle_extreme = bool(bornes and (ratio < bornes[0] or ratio > bornes[1]))
    if regle_extreme:
        facteurs.append("Prix par m² situé dans un extrême du jeu d'entraînement")
    for colonne, libelle in (("log_surface", "Surface"), ("nb_pieces", "Nombre de pièces")):
        low, high = artefact["quantiles"][colonne]
        if a[colonne] < low or a[colonne] > high:
            facteurs.append(f"{libelle} hors de la plage centrale des annonces d'entraînement")
    if artefact["frequences"].get("ville", {}).get(a.ville, 0) < .01:
        facteurs.append("Ville rare ou absente des annonces d'entraînement")
    atypique = score >= artefact["seuil"] or regle_extreme
    return {"disponible": True, "score_anomalie": round(percentile, 3), "niveau": "à_verifier" if atypique else "habituel",
            "seuil_validation": round(float(np.searchsorted(reference, artefact["seuil"], side="right") / len(reference)), 3),
            "facteurs": facteurs, "interpretation": "Score relatif de atypicité, pas une probabilité ni une preuve de fraude."}
