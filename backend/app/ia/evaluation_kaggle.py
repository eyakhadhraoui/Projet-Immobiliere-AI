"""Évaluation de l'estimation du prix sur des ventes RÉELLES (jeu Kaggle « Tunisian House Prices Prediction »).

Module de COMPARAISON seulement (IA-ANNONCE-002-KAGGLE) : il ne modifie pas l'estimation utilisée par
l'application (toujours entraînée par ``flask --app run entrainer-prix``). Il répond à trois questions :

1. RÉFÉRENCE : que vaut le système existant (``estimation_prix``, appelé sans aucune modification) sur des
   ventes réelles plutôt que sur nos données de démonstration ?
2. AMÉLIORATIONS : des pistes proposées (variables supplémentaires disponibles dans ces données, modèle de
   gradient boosting) font-elles mieux ? Le choix se fait par validation croisée sur l'entraînement,
   exactement comme dans le système existant, jamais sur le test.
3. AVANT / APRÈS : comparaison sur EXACTEMENT les mêmes annonces de test.

Données : 5 678 ventes (``train.csv`` de la compétition), avec prix. ``test.csv`` n'a pas de prix (gardés par
Kaggle) : il ne sert pas ici. Pas de type de bien ni de location dans ces données ; la colonne ``garden`` vaut 0
partout. Usage académique autorisé (confirmé par l'étudiante) ; les fichiers bruts restent hors du dépôt Git.
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ia import estimation_prix as ep

# Colonnes indispensables de train.csv (contrôlées à la lecture : un autre fichier est refusé clairement).
COLONNES_KAGGLE = (
    "Id", "price_tnd", "city", "governorate", "Area", "pieces", "room", "bathroom", "age", "state", "latt", "long",
    "distance_to_capital", "garage", "garden", "concierge", "beach_view", "mountain_view", "pool", "elevator",
    "furnished", "equipped_kitchen", "central_heating", "air_conditioning",
)
# Correspondance avec les équipements de notre formulaire (balcon et internet n'existent pas dans ces données).
EQUIPEMENTS_KAGGLE = {"garage": "parking", "air_conditioning": "climatisation", "elevator": "ascenseur",
                      "garden": "jardin", "pool": "piscine", "central_heating": "chauffage"}
# Le jeu n'indique pas le type de bien : valeur constante (sans effet sur les modèles), choisie parmi nos types
# pour que le système existant puisse être appelé tel quel.
TYPE_PAR_DEFAUT = "appartement"
# Âge en tranches (texte) → milieu de la tranche, en années.
AGES = {"0": 0.0, "1-5": 3.0, "5-10": 7.5, "10-20": 15.0, "10,20": 15.0, "20-30": 25.0, "30-50": 40.0,
        "50-70": 60.0, "70-100": 85.0, "plus de 100": 110.0}
# Variables présentes dans ces données mais pas dans notre formulaire : la piste d'amélioration « plus d'informations ».
VARIABLES_AJOUTEES = ("chambres", "salles_de_bain", "etat", "age", "latitude", "longitude", "distance_capitale",
                      "conciergerie", "vue_mer", "vue_montagne", "cuisine_equipee")
DOSSIER_RESULTATS = "kaggle"


class FichierKaggleInvalide(Exception):
    """Le fichier fourni n'est pas le train.csv attendu (ou une archive qui le contient)."""


# --- 1. Lecture et adaptation au format des annonces ----------------------------------------------------------

def lire_kaggle(chemin: Path) -> pd.DataFrame:
    """Lit ``train.csv``, directement ou dans l'archive ``.zip`` téléchargée depuis Kaggle (sans l'extraire).

    Args:
        chemin: Fichier ``train.csv`` ou archive qui le contient.

    Returns:
        pd.DataFrame: Données brutes.

    Raises:
        FichierKaggleInvalide: Fichier absent, sans ``train.csv`` ou sans les colonnes attendues.
    """
    if not chemin.exists():
        raise FichierKaggleInvalide(f"Fichier introuvable : {chemin}")
    if chemin.suffix.lower() == ".zip":
        with zipfile.ZipFile(chemin) as archive:
            if "train.csv" not in archive.namelist():
                raise FichierKaggleInvalide(f"{chemin.name} ne contient pas train.csv.")
            donnees = pd.read_csv(io.BytesIO(archive.read("train.csv")))
    else:
        donnees = pd.read_csv(chemin)
    manquantes = [c for c in COLONNES_KAGGLE if c not in donnees.columns]
    if manquantes:
        raise FichierKaggleInvalide(f"Colonnes manquantes : {', '.join(manquantes)}")
    return donnees


def _nombre(valeur: Any) -> float | None:
    """Nombre ou ``None`` si la valeur est absente (NaN)."""
    return None if pd.isna(valeur) else float(valeur)


def _age(valeur: Any) -> float | None:
    """Tranche d'âge (« 1-5 », « Plus de 100 »…) → nombre d'années, ou ``None``."""
    if pd.isna(valeur):
        return None
    return AGES.get(" ".join(str(valeur).casefold().split()))


def vers_annonces(donnees: pd.DataFrame) -> list[dict[str, Any]]:
    """Transforme chaque ligne Kaggle en annonce au format du système existant (+ variables ajoutées).

    Ville : ``city``, ou à défaut le gouvernorat (18 % de ``city`` sont vides). Les variables du formulaire
    (surface, pièces, meublé, équipements) sont reprises telles quelles ; une valeur absente reste absente : c'est
    ``preparer_donnees`` (contrôle qualité existant) qui décide d'écarter l'annonce.

    Args:
        donnees: Lignes de ``train.csv``.

    Returns:
        list[dict[str, Any]]: Annonces.
    """
    annonces = []
    for ligne in donnees.to_dict("records"):
        gouvernorat = " ".join(str(ligne["governorate"]).split()) if not pd.isna(ligne["governorate"]) else None
        ville = " ".join(str(ligne["city"]).split()) if not pd.isna(ligne["city"]) else gouvernorat
        pieces = _nombre(ligne["pieces"])
        annonces.append({
            "id": int(ligne["Id"]), "titre": f"Kaggle {int(ligne['Id'])}", "transaction": "vente",
            "type_bien": TYPE_PAR_DEFAUT, "ville": ville, "surface": _nombre(ligne["Area"]),
            "nb_pieces": None if pieces is None else int(pieces), "meuble": bool(ligne["furnished"]),
            "caracteristiques": sorted(nom for colonne, nom in EQUIPEMENTS_KAGGLE.items() if ligne[colonne] == 1),
            "prix": _nombre(ligne["price_tnd"]),
            # Variables ajoutées (non utilisées par le système existant)
            "gouvernorat": gouvernorat or ville, "chambres": _nombre(ligne["room"]),
            "salles_de_bain": _nombre(ligne["bathroom"]), "etat": _nombre(ligne["state"]), "age": _age(ligne["age"]),
            "latitude": _nombre(ligne["latt"]), "longitude": _nombre(ligne["long"]),
            "distance_capitale": _nombre(ligne["distance_to_capital"]),
            "conciergerie": float(ligne["concierge"]), "vue_mer": float(ligne["beach_view"]),
            "vue_montagne": float(ligne["mountain_view"]), "cuisine_equipee": float(ligne["equipped_kitchen"]),
        })
    return annonces


def tableau_etendu(annonces: list[dict[str, Any]]) -> pd.DataFrame:
    """Variables du système existant + gouvernorat + variables ajoutées (les absentes restent NaN)."""
    tableau = ep.vers_tableau(annonces)
    tableau["gouvernorat"] = [ep.normaliser_ville(a["gouvernorat"]) for a in annonces]
    for nom in VARIABLES_AJOUTEES:
        tableau[nom] = [np.nan if a[nom] is None else a[nom] for a in annonces]
    return tableau


# --- 2. Améliorations proposées --------------------------------------------------------------------------------

def _pipeline(modele: Any, etendu: bool, imputer: bool) -> Pipeline:
    """Encodage one-hot des catégories ; valeurs absentes remplacées par la médiane (+ indicateur « était absent »)
    pour les modèles qui ne savent pas les gérer (régression linéaire, forêt). Le gradient boosting les gère seul."""
    categories = ["type_bien", "ville"] + (["gouvernorat"] if etendu else [])
    numeriques = ["surface", "log_surface", "nb_pieces", "meuble", *[f"eq_{n}" for n in ep.CARACTERISTIQUES]]
    if etendu:
        numeriques += list(VARIABLES_AJOUTEES)
    encodage = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categories),
        ("nombres", SimpleImputer(strategy="median", add_indicator=True) if imputer else "passthrough", numeriques),
    ])
    return Pipeline([("encodage", encodage), ("modele", modele)])


def ameliorations(nb_arbres: int, graine: int) -> dict[str, dict[str, Any]]:
    """Pistes d'amélioration comparées (une seule idée nouvelle à la fois, pour savoir ce qui aide).

    Args:
        nb_arbres: Nombre d'arbres de la forêt.
        graine: Graine aléatoire.

    Returns:
        dict: ``{nom: {"idee", "pipeline", "etendu"}}``.
    """
    return {
        "A1 LinearRegression + variables ajoutées": {
            "idee": "même modèle que le système retenu, avec les variables disponibles en plus",
            "pipeline": _pipeline(LinearRegression(), etendu=True, imputer=True), "etendu": True},
        "A2 HistGradientBoosting (variables d'origine)": {
            "idee": "modèle plus souple (interactions, seuils), mêmes variables que le système existant",
            "pipeline": _pipeline(HistGradientBoostingRegressor(random_state=graine), etendu=False, imputer=False),
            "etendu": False},
        "A3 HistGradientBoosting + variables ajoutées": {
            "idee": "les deux idées ensemble",
            "pipeline": _pipeline(HistGradientBoostingRegressor(random_state=graine), etendu=True, imputer=False),
            "etendu": True},
        "A4 RandomForest + variables ajoutées": {
            "idee": "forêt du système existant avec les variables ajoutées",
            "pipeline": _pipeline(RandomForestRegressor(n_estimators=nb_arbres, min_samples_leaf=ep.FEUILLE_MIN,
                                                        random_state=graine, n_jobs=1), etendu=True, imputer=True),
            "etendu": True},
    }


def mesures_completes(vrais: np.ndarray, predits: np.ndarray) -> dict[str, float]:
    """MAE, MAPE, R² (comme le système existant) + RMSE (métrique probable du classement Kaggle).

    RMSE = racine de la moyenne des erreurs au carré : elle pénalise fortement les grosses erreurs, donc les
    biens très chers.
    """
    return {**ep.mesures(vrais, predits), "rmse": round(float(math.sqrt(mean_squared_error(vrais, predits))), 2)}


def choisir_apres(lignes: dict[str, dict[str, Any]]) -> str:
    """Modèle retenu « après » : meilleure MAPE de validation croisée parmi l'existant et les pistes.

    Jamais d'après le test : choisir sur le test, puis annoncer ce score, serait tricher (le test ne serait plus
    une mesure indépendante). La baseline (sans validation croisée) n'est pas candidate.

    Args:
        lignes: Résultats par modèle (``cv`` = MAPE de validation croisée, ou ``None``).

    Returns:
        str: Nom du modèle retenu.
    """
    candidats = {n: l["cv"] for n, l in lignes.items() if l["cv"] is not None}
    return min(candidats, key=candidats.get)


def lire_classement(chemin: Path) -> list[dict[str, float]]:
    """Scores du classement privé Kaggle : on ne garde QUE le rang et le score (aucun nom ni pseudonyme).

    Args:
        chemin: CSV du classement.

    Returns:
        list[dict[str, float]]: ``[{"rang", "score"}]`` trié par rang.
    """
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        lignes = [{"rang": int(l["Rank"]), "score": float(l["Score"])} for l in csv.DictReader(fichier)]
    return sorted(lignes, key=lambda l: l["rang"])


# --- 3. Évaluation avant / après -------------------------------------------------------------------------------

def evaluer(
    chemin: Path,
    dossier: Path,
    nb_arbres: int = ep.NB_ARBRES,
    graine: int = ep.GRAINE,
    nb_plis: int = ep.NB_PLIS,
    chemin_classement: Path | None = None,
) -> dict[str, Any]:
    """Établit la référence du système existant, évalue les améliorations, compare avant / après.

    Args:
        chemin: ``train.csv`` ou archive Kaggle.
        dossier: Dossier des modèles (le rapport est écrit dans ``dossier/kaggle``).
        nb_arbres: Nombre d'arbres des forêts.
        graine: Graine aléatoire.
        nb_plis: Plis de la validation croisée.
        chemin_classement: CSV du classement privé (facultatif, repère indicatif).

    Returns:
        dict[str, Any]: Résultats (aussi enregistrés en JSON et en Markdown).
    """
    brutes = lire_kaggle(chemin)
    doublons_bruts = int(brutes.drop(columns="Id").duplicated().sum())
    # Même contrôle qualité que le système existant : incomplètes, prix au m² aberrants, doublons.
    annonces, qualite = ep.preparer_donnees(vers_annonces(brutes))

    # AVANT : le système existant, appelé SANS modification (mêmes variables, mêmes modèles, même choix).
    avant = ep.entrainer_transaction(annonces, nb_arbres, graine, nb_plis)

    # Même séparation que celle faite à l'intérieur d'entrainer_transaction (même appel, même graine) :
    # avant et après sont mesurés sur EXACTEMENT les mêmes annonces de test.
    pos_app, pos_test = train_test_split(np.arange(len(annonces)), test_size=ep.PART_TEST, random_state=graine)
    app, test = [annonces[i] for i in pos_app], [annonces[i] for i in pos_test]
    separation = ep.verifier_separation(app, test)
    prix_app = np.array([a["prix"] for a in app], dtype=float)
    prix_test = np.array([a["prix"] for a in test], dtype=float)
    base_app, base_test = ep.vers_tableau(app), ep.vers_tableau(test)
    etendu_app, etendu_test = tableau_etendu(app), tableau_etendu(test)

    predits_baseline = ep.baseline(base_app, prix_app, base_test)
    predits_avant = np.exp(avant.modele["pipeline"].predict(base_test))
    lignes = {
        "baseline (prix médian au m² de la ville × surface)": {
            "role": "référence sans IA", "test": mesures_completes(prix_test, predits_baseline), "cv": None},
        f"AVANT : système existant ({avant.nom_modele})": {
            "role": "avant", "test": mesures_completes(prix_test, predits_avant),
            "cv": avant.mape_validation_croisee[avant.nom_modele]},
    }

    plis = KFold(n_splits=nb_plis, shuffle=True, random_state=graine)
    predits_apres: dict[str, np.ndarray] = {}
    for nom, piste in ameliorations(nb_arbres, graine).items():
        x_app, x_test = (etendu_app, etendu_test) if piste["etendu"] else (base_app, base_test)
        cv = cross_val_predict(piste["pipeline"], x_app, np.log(prix_app), cv=plis)
        pipeline = piste["pipeline"].fit(x_app, np.log(prix_app))
        predits_apres[nom] = np.exp(pipeline.predict(x_test))
        lignes[nom] = {"role": "amelioration", "idee": piste["idee"],
                       "test": mesures_completes(prix_test, predits_apres[nom]),
                       "cv": ep._mape(prix_app, np.exp(cv))}

    retenu = choisir_apres(lignes)
    lignes[retenu]["retenu"] = True
    predits_retenu = predits_avant if lignes[retenu]["role"] == "avant" else predits_apres[retenu]
    gouvernorats = [a["gouvernorat"].title() for a in test]

    resultats = {
        "evalue_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"fichier": chemin.name, "lignes": len(brutes), "doublons_exacts_bruts_hors_id": doublons_bruts,
                   "usage": "académique, autorisé (confirmé par l'étudiante)"},
        "versions": {"scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "parametres": {"graine": graine, "nb_plis": nb_plis, "nb_arbres": nb_arbres, "part_test": ep.PART_TEST},
        "qualite_donnees": qualite,
        "separation": separation,
        "modeles": lignes,
        "retenu_apres": retenu,
        "mape_par_gouvernorat": {
            "avant": ep.mape_par_groupe(prix_test, predits_avant, predits_baseline, gouvernorats),
            "apres": ep.mape_par_groupe(prix_test, predits_retenu, predits_baseline, gouvernorats),
        },
    }
    if chemin_classement is not None:
        scores = [l["score"] for l in lire_classement(chemin_classement)]
        resultats["classement_kaggle"] = {"nb_equipes": len(scores), "meilleur": min(scores),
                                          "median": float(np.median(scores)), "dernier": max(scores),
                                          "scores": scores}
    sortie = dossier / DOSSIER_RESULTATS
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "evaluation_kaggle.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")
    (sortie / "EVALUATION_KAGGLE.md").write_text(rapport(resultats), encoding="utf-8")
    return resultats


def rapport(r: dict[str, Any]) -> str:
    """Rapport Markdown de la comparaison avant / après.

    Args:
        r: Résultats de ``evaluer``.

    Returns:
        str: Contenu de ``EVALUATION_KAGGLE.md``.
    """
    q = r["qualite_donnees"]
    lignes = [
        "# Évaluation sur des ventes réelles (Kaggle « Tunisian House Prices Prediction »)",
        "",
        f"Générée le {r['evalue_le']} (UTC). Comparaison seulement : l'estimation de l'application n'est pas "
        "modifiée.",
        "",
        "## Données",
        "",
        f"- Source : `{r['source']['fichier']}` (train.csv), {r['source']['lignes']} ventes ; usage "
        f"{r['source']['usage']}.",
        f"- Contrôle qualité du système existant : {q['nb_annonces_utilisables']} annonces utilisables ; "
        f"{q['nb_incompletes_exclues']} incomplètes (surtout nombre de pièces ou surface absents), "
        f"{q['aberrantes']['nb']} prix au m² aberrants, {q['doublons']['nb']} doublons exclus.",
        f"- Séparation : {r['separation']['nb_entrainement']} entraînement / {r['separation']['nb_test']} test, "
        "aucune annonce commune (vérifié) ; avant et après sont mesurés sur les mêmes annonces de test.",
        "- Ces données sont des ventes uniquement, sans type de bien ; balcon et internet n'existent pas ; "
        "jardin vaut 0 partout.",
        "",
        "## Avant / après (jeu de test)",
        "",
        "| Modèle | MAE (TND) | MAPE (%) | R² | RMSE (TND) | MAPE val. croisée (%) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for nom, l in r["modeles"].items():
        t = l["test"]
        lignes.append(f"| {nom}{' **(retenu)**' if l.get('retenu') else ''} | {t['mae']:,.0f} | {t['mape']:.1f} | "
                      f"{t['r2']:.3f} | {t['rmse']:,.0f} | {'—' if l['cv'] is None else format(l['cv'], '.1f')} |"
                      .replace(",", " "))
    lignes += ["", "Choix « après » : plus faible MAPE de validation croisée (entraînement seulement).", ""]
    lignes += ["## MAPE par gouvernorat (test)", "", "| Gouvernorat | n | Avant (%) | Après (%) |", "|---|---:|---:|---:|"]
    apres = r["mape_par_gouvernorat"]["apres"]
    for g, v in r["mape_par_gouvernorat"]["avant"].items():
        lignes.append(f"| {g} | {v['n']} | {v['mape']:.1f} | {apres[g]['mape']:.1f} |")
    if "classement_kaggle" in r:
        c = r["classement_kaggle"]
        milliers = lambda v: f"{v:,.0f}".replace(",", " ")  # noqa: E731 — 450603 → « 450 603 »
        lignes += ["", "## Repère : classement privé Kaggle", "",
                   f"{c['nb_equipes']} équipes ; score (métrique non précisée dans le fichier, probablement RMSE en TND) : "
                   f"meilleur {milliers(c['meilleur'])}, médiane {milliers(c['median'])}, dernier {milliers(c['dernier'])}.",
                   "Repère indicatif seulement : leurs scores portent sur les 738 annonces cachées de test.csv, les "
                   "nôtres sur une partie de train.csv ; ce ne sont pas les mêmes annonces."]
    return "\n".join(lignes) + "\n"
