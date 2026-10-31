"""Classement local des annonces avec LightGBM LambdaRank et contributions SHAP."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

VERSION_MODELE = 1
logger = logging.getLogger(__name__)
NOMS_CARACTERISTIQUES = (
    "ville_exacte", "type_exact", "transaction_exacte", "prix_dans_budget",
    "ecart_prix", "surface_suffisante", "ecart_surface", "meuble_exact",
    "prix_relatif_budget", "surface_confort",
)
VILLES = ("Tunis", "La Marsa", "Sousse", "Sfax", "Hammamet", "Nabeul")
TYPES = ("appartement", "maison", "studio", "villa", "residence")
TRANSACTIONS = ("location", "vente")


def caracteristiques(annonce: dict[str, Any], criteres: dict[str, Any]) -> list[float]:
    """Construit les variables de compatibilité entre une annonce et une recherche."""
    ville = str(criteres.get("ville") or "").strip().casefold()
    type_bien = str(criteres.get("type_bien") or "")
    transaction = str(criteres.get("transaction") or "")
    prix = float(annonce.get("prix") or 0)
    surface = float(annonce.get("surface") or 0)
    prix_min = criteres.get("prix_min")
    prix_max = criteres.get("prix_max")
    surface_min = criteres.get("surface_min")
    dans_budget = prix_min is None or prix >= float(prix_min)
    dans_budget = dans_budget and (prix_max is None or prix <= float(prix_max))
    ecart_prix = 0.0
    if prix_min is not None and prix < float(prix_min):
        ecart_prix = (float(prix_min) - prix) / max(float(prix_min), 1.0)
    elif prix_max is not None and prix > float(prix_max):
        ecart_prix = (prix - float(prix_max)) / max(float(prix_max), 1.0)
    surface_suffisante = surface_min is None or surface >= float(surface_min)
    ecart_surface = (
        max(0.0, float(surface_min) - surface) / max(float(surface_min), 1.0)
        if surface_min is not None else 0.0
    )
    meuble = criteres.get("meuble")
    budget_reference = float(prix_max) if prix_max is not None else (
        2000.0 if annonce.get("transaction") == "location" else 600000.0
    )
    surface_reference = float(surface_min) if surface_min is not None else 80.0
    return [
        float(not ville or ville in str(annonce.get("ville") or "").strip().casefold()),
        float(not type_bien or annonce.get("type_bien") == type_bien),
        float(not transaction or annonce.get("transaction") == transaction),
        float(dans_budget), min(1.0, ecart_prix), float(surface_suffisante),
        min(1.0, ecart_surface), float(meuble is None or annonce.get("meuble") is bool(meuble)),
        min(2.0, prix / max(budget_reference, 1.0)),
        min(3.0, surface / max(surface_reference, 1.0)),
    ]


def _pertinence_synthetique(vecteur: Sequence[float]) -> int:
    """Produit une étiquette de compatibilité pour le jeu simulé, pas un jugement humain."""
    points = 0.0
    for index, poids in ((0, 3.0), (1, 2.5), (2, 2.0), (3, 2.5), (5, 1.5), (7, 0.5)):
        points += poids * vecteur[index]
    points -= 1.0 * vecteur[4] + 0.8 * vecteur[6]
    points -= 0.8 * vecteur[8]
    points += 0.5 * vecteur[9]
    return 3 if points >= 10 else 2 if points >= 7 else 1 if points >= 4 else 0


def generer_jeu_simule(nb_recherches: int = 320, annonces_par_recherche: int = 12,
                       graine: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Crée des groupes recherche-annonces synthétiques pour entraîner LambdaRank."""
    rng = random.Random(graine)
    matrices: list[list[float]] = []
    etiquettes: list[int] = []
    groupes: list[int] = []
    for _ in range(nb_recherches):
        criteres = {
            "ville": rng.choice(VILLES) if rng.random() < 0.75 else "",
            "type_bien": rng.choice(TYPES) if rng.random() < 0.7 else "",
            "transaction": rng.choice(TRANSACTIONS) if rng.random() < 0.8 else "",
            "prix_min": rng.choice((None, None, 500, 800, 100000, 250000)),
            "prix_max": rng.choice((None, 900, 1500, 180000, 400000, 900000)),
            "surface_min": rng.choice((None, None, 30, 60, 100, 160)),
            "meuble": rng.choice((None, None, True, False)),
        }
        for _ in range(annonces_par_recherche):
            is_rent = rng.choice((True, False))
            annonce = {
                "ville": rng.choice(VILLES), "type_bien": rng.choice(TYPES),
                "transaction": "location" if is_rent else "vente",
                "prix": rng.randint(400, 3000) if is_rent else rng.randint(70000, 1000000),
                "surface": rng.randint(20, 400), "meuble": rng.choice((True, False)),
            }
            x = caracteristiques(annonce, criteres)
            matrices.append(x)
            etiquettes.append(_pertinence_synthetique(x))
        groupes.append(annonces_par_recherche)
    return np.asarray(matrices, dtype=float), np.asarray(etiquettes, dtype=int), np.asarray(groupes, dtype=int)


def entrainer(dossier_modeles: Path, graine: int = 42) -> dict[str, Any]:
    """Entraîne LambdaRank avec des groupes simulés et enregistre l'artefact local."""
    try:
        from lightgbm import LGBMRanker
    except ImportError as erreur:
        raise RuntimeError("LightGBM est facultatif; installez backend/requirements-ia.txt.") from erreur
    X, y, groupes = generer_jeu_simule(graine=graine)
    modele = LGBMRanker(
        objective="lambdarank", metric="ndcg", n_estimators=120, learning_rate=0.05,
        num_leaves=15, random_state=graine, verbosity=-1,
    )
    modele.fit(X, y, group=groupes.tolist(), feature_name=list(NOMS_CARACTERISTIQUES))
    dossier_modeles.mkdir(parents=True, exist_ok=True)
    chemin = dossier_modeles / "classement_annonces.joblib"
    joblib.dump({"version": VERSION_MODELE, "modele": modele}, chemin)
    metadata = {
        "version": VERSION_MODELE, "source": "donnees_simulees", "nb_recherches": len(groupes),
        "nb_annonces": len(y), "graine": graine, "fonctionnalites": list(NOMS_CARACTERISTIQUES),
    }
    (dossier_modeles / "classement_annonces.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**metadata, "chemin": str(chemin)}


def classer(annonces: list[dict[str, Any]], criteres: dict[str, Any],
            dossier_modeles: Path) -> tuple[list[dict[str, Any]], bool]:
    """Classe les annonces par pertinence, ou garde leur ordre chronologique si le modèle manque."""
    chemin = dossier_modeles / "classement_annonces.joblib"
    if not annonces:
        return annonces, False
    if not chemin.is_file():
        logger.warning("Artefact LambdaRank absent (%s); le classement chronologique est utilisé.", chemin.name)
        return annonces, False
    try:
        artefact = joblib.load(chemin)
        if artefact.get("version") != VERSION_MODELE:
            logger.warning("Version de l'artefact LambdaRank incompatible; repli chronologique.")
            return annonces, False
        modele = artefact["modele"]
        X = pd.DataFrame(
            [caracteristiques(a, criteres) for a in annonces], columns=NOMS_CARACTERISTIQUES
        )
        scores = modele.predict(X)
        contributions = modele.booster_.predict(X, pred_contrib=True)
        for annonce, score, valeurs in zip(annonces, scores, contributions, strict=True):
            explications = sorted(
                ((NOMS_CARACTERISTIQUES[i], float(valeurs[i])) for i in range(len(NOMS_CARACTERISTIQUES))
                 if valeurs[i] > 0), key=lambda element: element[1], reverse=True,
            )[:3]
            annonce["classement_ia"] = {
                "score": round(float(score), 4),
                "explications": [{"caracteristique": nom, "influence": round(influence, 4)}
                                 for nom, influence in explications],
            }
        return sorted(annonces, key=lambda annonce: annonce["classement_ia"]["score"], reverse=True), True
    except Exception:  # noqa: BLE001 - repli déterministe si artefact/librairie invalide
        logger.exception("Erreur du classement LambdaRank; le classement chronologique est utilisé.")
        return annonces, False


def evaluer_simule(graine: int = 73, repetitions_bootstrap: int = 1000) -> dict[str, Any]:
    """Compare LambdaRank au hasard chronologique sur validation simulée, avec IC bootstrap."""
    try:
        from lightgbm import LGBMRanker
    except ImportError as erreur:
        raise RuntimeError("LightGBM est facultatif; installez backend/requirements-ia.txt.") from erreur
    X, y, groupes = generer_jeu_simule(nb_recherches=180, graine=graine)
    limites = np.cumsum(np.r_[0, groupes])
    ids = list(range(len(groupes)))
    random.Random(graine).shuffle(ids)
    n_train = int(len(ids) * 0.7)
    train_ids, validation_ids = ids[:n_train], ids[n_train:]
    train_x = np.concatenate([X[limites[i]:limites[i + 1]] for i in train_ids])
    train_y = np.concatenate([y[limites[i]:limites[i + 1]] for i in train_ids])
    train_group = [int(groupes[i]) for i in train_ids]
    modele = LGBMRanker(objective="lambdarank", metric="ndcg", n_estimators=100,
                        learning_rate=0.05, num_leaves=15, random_state=graine, verbosity=-1)
    modele.fit(train_x, train_y, group=train_group)
    differences: list[float] = []
    for index in validation_ids:
        debut, fin = int(limites[index]), int(limites[index + 1])
        relevances = y[debut:fin]
        predicted = modele.predict(X[debut:fin])
        regles = np.asarray([_pertinence_synthetique(ligne) for ligne in X[debut:fin]])
        ordre_regles = np.argsort(-regles, kind="stable")
        differences.append(_ndcg(relevances, np.argsort(-predicted)) - _ndcg(relevances, ordre_regles))
    rng = np.random.default_rng(graine)
    echantillons = np.asarray(differences)
    moyennes = np.asarray([
        rng.choice(echantillons, size=len(echantillons), replace=True).mean()
        for _ in range(repetitions_bootstrap)
    ])
    borne_basse, borne_haute = np.quantile(moyennes, [0.025, 0.975]).tolist()
    return {
        "type_donnees": "simulees", "nb_recherches_validation": len(differences),
        "gain_ndcg_moyen": round(float(echantillons.mean()), 4),
        "intervalle_confiance_95": [round(float(borne_basse), 4), round(float(borne_haute), 4)],
        "amelioration_statistiquement_significative": bool(borne_basse > 0),
        "avertissement": "Données simulées : ces résultats ne démontrent aucun gain sur de vrais visiteurs.",
    }


def _ndcg(relevances: np.ndarray, ordre: np.ndarray, k: int = 5) -> float:
    """Calcule NDCG@k pour une liste d'étiquettes de pertinence graduées."""
    gains = np.power(2.0, relevances[ordre[:k]]) - 1.0
    discounts = np.log2(np.arange(2, len(gains) + 2))
    dcg = float(np.sum(gains / discounts))
    ideal = float(np.sum((np.power(2.0, np.sort(relevances)[::-1][:k]) - 1.0) / discounts))
    return dcg / ideal if ideal > 0 else 0.0
