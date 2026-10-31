"""Estimation du prix d'une annonce par apprentissage automatique (IA-ANNONCE-001).

Tout est entraîné et exécuté localement avec scikit-learn : aucune API d'IA externe, aucun appel réseau.

Plan (à suivre à l'oral) :
1. PRÉPARATION : on écarte les prix aberrants (nettoyage), puis chaque annonce devient une ligne de tableau
   (variables) ; la cible est log(prix).
   Pourquoi le logarithme ? Les prix vont de 300 TND (loyer d'un studio) à plus d'un million (villa) : le log
   « écrase » ces écarts et transforme les effets multiplicatifs (« +15 % si meublé ») en effets additifs,
   plus faciles à apprendre. Pour la même raison, on donne aussi log(surface) : le prix étant proportionnel à la
   surface, log(prix) varie LINÉAIREMENT avec log(surface) (et non avec la surface brute).
2. DEUX MODÈLES SÉPARÉS : un pour la location (loyer mensuel), un pour la vente : ce ne sont pas les mêmes ordres
   de grandeur ni les mêmes logiques.
3. ÉVALUATION HONNÊTE : 80 % des annonces pour apprendre, 20 % cachées pour le test final. On compare :
   - une baseline simple : « prix médian au m² de la ville × surface » (ce que ferait une personne sans IA) ;
   - une régression linéaire ;
   - une forêt aléatoire (Random Forest).
   Le choix entre les deux modèles se fait par validation croisée sur les 80 % (jamais sur le test).
4. PRÉDICTION : prix estimé, fourchette (10e et 90e centiles des arbres de la forêt) et facteurs principaux
   (on simule « avec / sans » chaque caractéristique et on mesure l'écart de prix).

Robustesse (IA-ANNONCE-001-ROBUSTE) :
5. QUALITÉ DES DONNÉES : avant l'entraînement, un rapport (effectifs, valeurs manquantes, doublons, annonces
   exclues et règle) est enregistré dans les métadonnées ; on vérifie qu'aucune annonce n'est à la fois dans
   l'entraînement et dans le test (sinon le score de test serait trop optimiste : « fuite de données »).
6. ÉVALUATION DÉTAILLÉE : MAPE par ville et par type de bien sur le test, pour montrer où le modèle est moins fiable.
7. CONFIANCE : chaque estimation dit si elle est fiable (« élevée », « moyenne », « faible ») et pourquoi : un modèle
   ne sait pas qu'il ne sait pas ; ville jamais vue ou surface hors de la plage apprise = il extrapole.
8. ÉLAGAGE (pruning) : on compare la forêt complète à une forêt plus petite (moins d'arbres, profondeur et taille
   des feuilles limitées) : taille du fichier, temps de réponse, précision.
9. FICHE DU MODÈLE (model card) : FICHE_MODELE.md, régénérée à chaque entraînement.

IMPORTANT : les annonces d'entraînement sont des données de DÉMONSTRATION générées par des règles
(``donnees_demo.py``). Les scores mesurent la capacité du modèle à retrouver ces règles, PAS la précision d'une
estimation sur le marché immobilier réel.
"""

from __future__ import annotations

import io
import json
import math
import platform
import statistics
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ia.donnees_demo import PREFIXE_TITRE

# --- Constantes ------------------------------------------------------------------------------------------------

TRANSACTIONS = ("location", "vente")
# Équipements utilisés comme variables (mêmes valeurs que les cases à cocher du formulaire d'annonce).
CARACTERISTIQUES = ("parking", "climatisation", "ascenseur", "balcon", "jardin", "piscine", "chauffage", "internet")
LIBELLES_CARACTERISTIQUES = {
    "parking": "Parking", "climatisation": "Climatisation", "ascenseur": "Ascenseur", "balcon": "Balcon",
    "jardin": "Jardin", "piscine": "Piscine", "chauffage": "Chauffage", "internet": "Internet",
}
LIBELLES_TYPES = {"appartement": "Appartement", "maison": "Maison", "studio": "Studio", "villa": "Villa",
                  "residence": "Résidence"}

PART_TEST = 0.20          # 20 % des annonces réservées au test final
NB_PLIS = 5               # validation croisée en 5 plis
NB_ARBRES = 200           # taille de la forêt
FEUILLE_MIN = 2           # au moins 2 annonces par feuille : limite l'apprentissage « par cœur »
MIN_ANNONCES = 30         # en dessous, on refuse d'entraîner (résultats non significatifs)
GRAINE = 2026             # graine fixe : mêmes résultats à chaque entraînement
CENTILES_FOURCHETTE = (10, 90)
NB_FACTEURS = 4
EFFET_MIN_POURCENT = 1    # un facteur de moins de 1 % n'est pas affiché

# Nettoyage : prix au m² plausibles (TND/m² pour une vente, TND/m²/mois pour une location). En dehors, l'annonce
# est considérée comme une erreur de saisie (ex. une vente à 41 TND) et exclue de l'entraînement.
BORNES_PRIX_M2 = {"location": (1.0, 100.0), "vente": (200.0, 20000.0)}
REGLE_ABERRANTES = ("prix au m² hors des bornes plausibles : location 1–100 TND/m²/mois, "
                    "vente 200–20 000 TND/m²")
# Champs sans lesquels une annonce ne peut pas servir à l'entraînement (variables + cible).
CHAMPS_REQUIS = ("type_bien", "transaction", "ville", "surface", "nb_pieces", "prix")

# Élagage (pruning) de la forêt : version « complète » = NB_ARBRES arbres, profondeur libre, feuilles de 2 annonces ;
# version « élaguée » = 4 fois moins d'arbres, profondeur 8 au plus, au moins 5 annonces par feuille.
PROFONDEUR_MAX_ELAGUEE = 8
FEUILLE_MIN_ELAGUEE = 5
DIVISEUR_ARBRES_ELAGUEE = 4
# La version élaguée est retenue si elle ne perd pas plus de 1 point de MAPE en validation croisée
# (décision prise sur les 80 % d'entraînement, jamais sur le test).
PERTE_MAX_ELAGAGE = 1.0

# Confiance : règles simples et explicables (voir _confiance).
LARGEUR_MOYENNE = 0.50    # fourchette plus large que 50 % du prix estimé → confiance moyenne
LARGEUR_FAIBLE = 0.80     # plus large que 80 % → confiance faible
VILLE_MIN_ANNONCES = 5    # ville vue moins de 5 fois à l'entraînement → confiance moyenne
FACTEUR_LARGEUR_REELLE = 1.25  # données réelles : « faible » si la fourchette dépasse 1,25 × la largeur typique

AVERTISSEMENT = ("Estimation indicative, calculée sur des données de démonstration. "
                 "Elle ne remplace pas l'avis d'un professionnel.")
AVERTISSEMENT_FAIBLE = "Estimation peu fiable pour ce bien : à utiliser avec prudence."

# Source des données d'entraînement (IA-ANNONCE-PPT-001) : démonstration générée ou annonces réelles importées.
SOURCE_DEMO = "demonstration"
SOURCE_REELLE = "annonces_reelles"
AVERTISSEMENT_REEL = ("Estimation indicative, calculée sur des annonces réelles publiées en ligne (prix affichés, "
                      "pas prix de vente conclus). Elle ne remplace pas l'avis d'un professionnel.")
# Les annonces réelles ne distinguent pas studio / résidence / appartement, ni maison / villa : on estime avec le
# type le plus proche connu du modèle (et on le signale dans la confiance).
TYPES_EQUIVALENTS_REELS = {"studio": "appartement", "residence": "appartement", "villa": "maison"}
# Les annonces réelles n'indiquent ni équipements ni meublé : leurs effets sont repris des données de démonstration.
MENTION_AJUSTEMENT = " (effet repris des données de démonstration)"
COLONNES_AJUSTABLES = ("meuble", *[f"eq_{nom}" for nom in CARACTERISTIQUES])
FICHIER_METADONNEES = "prix_metadonnees.json"
FICHIER_FICHE = "FICHE_MODELE.md"
MAX_EXCLUES_AFFICHEES = 30  # au-delà, la fiche renvoie aux métadonnées (données réelles : centaines d'exclusions)


class ModeleIndisponible(Exception):
    """Le modèle n'a pas été entraîné (fichiers absents) ou ne peut pas être chargé."""


class DonneesInsuffisantes(Exception):
    """Pas assez d'annonces pour entraîner un modèle fiable."""


class FuiteDeDonnees(Exception):
    """Une annonce se retrouve à la fois dans l'entraînement et dans le test (évaluation faussée)."""


# --- 1. Préparation des données --------------------------------------------------------------------------------

def normaliser_ville(ville: str) -> str:
    """Clé de ville insensible à la casse, aux accents et aux espaces (« la  MARSA » = « La Marsa »).

    Args:
        ville: Ville saisie.

    Returns:
        str: Clé normalisée.
    """
    sans_accents = unicodedata.normalize("NFKD", ville).encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.casefold().split())


def vers_tableau(annonces: list[dict[str, Any]]) -> pd.DataFrame:
    """Transforme des annonces en tableau de variables (une ligne par annonce).

    Variables : type de bien et ville (catégories, encodées plus loin en « one-hot »), surface et log(surface),
    nombre de pièces, meublé (0/1) et un indicateur 0/1 par équipement (« multi-hot »). Le nombre de salles de
    bain (``nb_sdb``) n'est ajouté que si TOUTES les annonces le renseignent (annonces réelles, ou annonces passées
    par ``adapter_au_modele`` pour un modèle qui l'utilise).

    Args:
        annonces: Dictionnaires avec type_bien, ville, surface, nb_pieces, meuble, caracteristiques (et nb_sdb).

    Returns:
        pd.DataFrame: Tableau des variables.
    """
    avec_sdb = bool(annonces) and all(a.get("nb_sdb") is not None for a in annonces)
    lignes = []
    for annonce in annonces:
        equipements = set(annonce.get("caracteristiques") or [])
        ligne = {
            "type_bien": annonce["type_bien"],
            "ville": normaliser_ville(annonce["ville"]),
            "surface": float(annonce["surface"]),
            "log_surface": math.log(float(annonce["surface"])),  # relation proportionnelle prix ↔ surface
            "nb_pieces": float(annonce["nb_pieces"]),
            "meuble": float(bool(annonce.get("meuble"))),
        }
        ligne.update({f"eq_{nom}": float(nom in equipements) for nom in CARACTERISTIQUES})
        if avec_sdb:
            ligne["nb_sdb"] = float(annonce["nb_sdb"])
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def adapter_au_modele(annonces: list[dict[str, Any]], modele: dict[str, Any]) -> list[dict[str, Any]]:
    """Met des annonces au format attendu par un modèle déjà entraîné, avant ``vers_tableau``.

    - type de bien : remplacé par son équivalent si le modèle ne le connaît pas (ex. villa → maison) ;
    - salles de bain : si le modèle les utilise et que la valeur manque (champ facultatif, annonces de la base),
      on prend la médiane observée à l'entraînement pour ce nombre de pièces ; si le modèle ne les utilise pas
      (modèle de démonstration), la valeur est retirée.

    Args:
        annonces: Annonces à estimer.
        modele: Contenu du fichier joblib.

    Returns:
        list[dict[str, Any]]: Copies adaptées (les annonces d'origine ne sont pas modifiées).
    """
    equivalents = modele.get("types_equivalents") or {}
    sdb = modele.get("sdb_par_defaut")
    adaptees = []
    for annonce in annonces:
        copie = {**annonce, "type_bien": equivalents.get(annonce["type_bien"], annonce["type_bien"])}
        if sdb is None:
            copie.pop("nb_sdb", None)
        elif copie.get("nb_sdb") is None:
            copie["nb_sdb"] = sdb["par_pieces"].get(int(copie["nb_pieces"]), sdb["global"])
        adaptees.append(copie)
    return adaptees


def _sdb_par_defaut(annonces: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Médiane du nombre de salles de bain par nombre de pièces (valeur de remplacement), ou None si absent."""
    if not annonces or any(a.get("nb_sdb") is None for a in annonces):
        return None
    par_pieces: dict[int, list[float]] = {}
    for annonce in annonces:
        par_pieces.setdefault(int(annonce["nb_pieces"]), []).append(float(annonce["nb_sdb"]))
    return {"par_pieces": {p: float(statistics.median(v)) for p, v in par_pieces.items()},
            "global": float(statistics.median(float(a["nb_sdb"]) for a in annonces))}


def construire_pipeline(modele: Any) -> Pipeline:
    """Chaîne de traitement : encodage one-hot (type, ville) puis le modèle.

    One-hot : la ville « Sousse » devient une colonne ville_sousse = 1 (0 pour les autres villes). Une ville
    inconnue à l'entraînement donne des 0 partout (handle_unknown="ignore") au lieu de faire planter la prédiction.

    Args:
        modele: Régresseur scikit-learn.

    Returns:
        Pipeline: Pipeline prêt à être entraîné.
    """
    encodage = ColumnTransformer(
        [("categories", OneHotEncoder(handle_unknown="ignore"), ["type_bien", "ville"])],
        remainder="passthrough",  # surface, pièces, meublé, équipements : utilisés tels quels
    )
    return Pipeline([("encodage", encodage), ("modele", modele)])


def filtrer_aberrantes(annonces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sépare les annonces au prix plausible de celles au prix aberrant (nettoyage des données).

    Exemple réel de la base : une « vente » à 41 TND pour 52 m² (0,79 TND/m²) est une annonce de test ; la garder
    fausserait l'apprentissage et ferait exploser la MAPE (erreur divisée par un prix minuscule).

    Args:
        annonces: Annonces avec transaction, prix et surface.

    Returns:
        tuple: (annonces gardées, annonces exclues).
    """
    gardees, exclues = [], []
    for annonce in annonces:
        bas, haut = BORNES_PRIX_M2[annonce["transaction"]]
        prix_m2 = float(annonce["prix"]) / float(annonce["surface"])
        (gardees if bas <= prix_m2 <= haut else exclues).append(annonce)
    return gardees, exclues


def _noms_villes(annonces: list[dict[str, Any]]) -> dict[str, str]:
    """Clé normalisée de ville → nom affiché le plus fréquent (« la marsa » → « La Marsa »)."""
    variantes: dict[str, Counter[str]] = {}
    for annonce in annonces:
        variantes.setdefault(normaliser_ville(annonce["ville"]), Counter())[annonce["ville"].strip()] += 1
    return {cle: compteur.most_common(1)[0][0] for cle, compteur in variantes.items()}


def _cle_doublon(annonce: dict[str, Any]) -> tuple[Any, ...]:
    """Deux annonces sont des doublons si toutes leurs variables ET leur prix sont identiques."""
    return (annonce["transaction"], annonce["type_bien"], normaliser_ville(annonce["ville"]),
            float(annonce["surface"]), int(annonce["nb_pieces"]), bool(annonce.get("meuble")),
            tuple(sorted(annonce.get("caracteristiques") or [])), float(annonce["prix"]))


def _manque(valeur: Any) -> bool:
    """Valeur absente : None ou chaîne vide."""
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def preparer_donnees(annonces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Contrôle qualité avant l'entraînement : écarte les annonces inutilisables et produit un rapport.

    Trois filtres, dans cet ordre :
    1. valeurs manquantes sur une variable ou sur le prix → annonce inutilisable ;
    2. prix au m² aberrant (``filtrer_aberrantes``) → erreur de saisie probable ;
    3. doublons exacts (mêmes variables et même prix) → on n'en garde qu'un. Pourquoi ? Si une copie tombait dans
       l'entraînement et l'autre dans le test, le modèle serait évalué sur une annonce déjà vue : score trop beau.

    Args:
        annonces: Annonces brutes (dictionnaires).

    Returns:
        tuple: (annonces utilisables, rapport de qualité enregistré dans les métadonnées).
    """
    manquantes = {champ: sum(_manque(a.get(champ)) for a in annonces) for champ in CHAMPS_REQUIS}
    completes = [a for a in annonces if not any(_manque(a.get(champ)) for champ in CHAMPS_REQUIS)]
    plausibles, aberrantes = filtrer_aberrantes(completes)
    vues: set[tuple[Any, ...]] = set()
    uniques, doublons = [], []
    for annonce in plausibles:
        cle = _cle_doublon(annonce)
        (doublons if cle in vues else uniques).append(annonce)
        vues.add(cle)

    noms = _noms_villes(uniques)
    rapport = {
        "nb_annonces_lues": len(annonces),
        "nb_annonces_utilisables": len(uniques),
        "provenance": {
            "demonstration_generee": sum(str(a.get("titre", "")).startswith(PREFIXE_TITRE) for a in uniques),
            "autres": sum(not str(a.get("titre", "")).startswith(PREFIXE_TITRE) for a in uniques),
        },
        "valeurs_manquantes": manquantes,
        "nb_incompletes_exclues": len(annonces) - len(completes),
        "aberrantes": {
            "regle": REGLE_ABERRANTES,
            "bornes_prix_m2": BORNES_PRIX_M2,
            "nb": len(aberrantes),
            "exclues": [{"titre": a.get("titre", "?"), "transaction": a["transaction"],
                         "prix_m2": round(float(a["prix"]) / float(a["surface"]), 2)} for a in aberrantes],
        },
        "doublons": {"regle": "mêmes variables et même prix : un seul exemplaire gardé", "nb": len(doublons)},
        "par_transaction": dict(Counter(a["transaction"] for a in uniques)),
        "par_ville": dict(Counter(noms[normaliser_ville(a["ville"])] for a in uniques).most_common()),
        "par_type": dict(Counter(a["type_bien"] for a in uniques).most_common()),
    }
    return uniques, rapport


# --- 2. Évaluation ---------------------------------------------------------------------------------------------

def mesures(vrais: np.ndarray, predits: np.ndarray) -> dict[str, float]:
    """Mesures d'erreur sur les prix (en TND, pas en log).

    - MAE : erreur moyenne absolue, en TND (« on se trompe en moyenne de … TND ») ;
    - MAPE : erreur moyenne en pourcentage du vrai prix (comparable entre location et vente) ;
    - R² : part de la variation des prix expliquée par le modèle (1 = parfait, 0 = pas mieux que la moyenne).

    Args:
        vrais: Prix réels.
        predits: Prix prédits.

    Returns:
        dict[str, float]: ``mae``, ``mape`` et ``r2``.
    """
    return {
        "mae": round(float(mean_absolute_error(vrais, predits)), 2),
        "mape": round(float(np.mean(np.abs(predits - vrais) / vrais) * 100), 2),
        "r2": round(float(r2_score(vrais, predits)), 3),
    }


def baseline(entrainement: pd.DataFrame, prix_entrainement: np.ndarray, a_predire: pd.DataFrame) -> np.ndarray:
    """Référence sans IA : prix médian au m² de la ville (sur l'entraînement) × surface.

    Une ville absente de l'entraînement utilise la médiane de toutes les villes.

    Args:
        entrainement: Variables des annonces d'entraînement.
        prix_entrainement: Prix des annonces d'entraînement.
        a_predire: Variables des annonces à estimer.

    Returns:
        np.ndarray: Prix estimés.
    """
    prix_m2 = pd.Series(prix_entrainement / entrainement["surface"].to_numpy(), index=entrainement.index)
    medianes = prix_m2.groupby(entrainement["ville"]).median()
    mediane_globale = float(prix_m2.median())
    par_ville = a_predire["ville"].map(medianes).fillna(mediane_globale).to_numpy()
    return par_ville * a_predire["surface"].to_numpy()


def _candidats(nb_arbres: int, graine: int) -> dict[str, Any]:
    """Modèles comparés (régression linéaire et forêt aléatoire « complète »)."""
    return {
        "LinearRegression": LinearRegression(),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=nb_arbres, min_samples_leaf=FEUILLE_MIN, random_state=graine, n_jobs=1
        ),
    }


def _foret_elaguee(nb_arbres: int, graine: int) -> RandomForestRegressor:
    """Forêt élaguée (pruning) : moins d'arbres, moins profonds, avec des feuilles plus grosses.

    Élaguer = limiter la complexité du modèle. Effets attendus : fichier plus petit et réponse plus rapide
    (moins de nœuds à parcourir), peut-être un peu moins précis. On le MESURE au lieu de le supposer.

    Args:
        nb_arbres: Nombre d'arbres de la forêt complète.
        graine: Graine aléatoire.

    Returns:
        RandomForestRegressor: Forêt élaguée (non entraînée).
    """
    return RandomForestRegressor(
        n_estimators=max(1, nb_arbres // DIVISEUR_ARBRES_ELAGUEE), max_depth=PROFONDEUR_MAX_ELAGUEE,
        min_samples_leaf=FEUILLE_MIN_ELAGUEE, random_state=graine, n_jobs=1,
    )


def _taille_octets(objet: Any) -> int:
    """Taille du fichier joblib qu'occuperait l'objet (mesurée en mémoire, sans écrire sur le disque)."""
    tampon = io.BytesIO()
    joblib.dump(objet, tampon)
    return tampon.getbuffer().nbytes


def _mape(vrais: np.ndarray, predits: np.ndarray) -> float:
    """MAPE en % (arrondie à 2 décimales)."""
    return round(float(np.mean(np.abs(predits - vrais) / vrais) * 100), 2)


def mape_par_groupe(
    vrais: np.ndarray, predits: np.ndarray, predits_baseline: np.ndarray, groupes: list[str]
) -> dict[str, dict[str, float]]:
    """MAPE du modèle et de la baseline pour chaque groupe (ville ou type), du moins fiable au plus fiable.

    À dire à l'oral : avec 2 ou 3 annonces de test dans un groupe, la MAPE varie beaucoup d'un tirage à l'autre ;
    l'effectif ``n`` est donc toujours donné à côté.

    Args:
        vrais: Prix réels du test.
        predits: Prix prédits par le modèle retenu.
        predits_baseline: Prix prédits par la baseline.
        groupes: Groupe de chaque annonce de test.

    Returns:
        dict: ``{groupe: {"n", "mape", "mape_baseline"}}`` trié par MAPE décroissante.
    """
    etiquettes = np.array(groupes)
    resultats = {}
    for groupe in sorted(set(groupes)):
        masque = etiquettes == groupe
        resultats[groupe] = {"n": int(masque.sum()), "mape": _mape(vrais[masque], predits[masque]),
                             "mape_baseline": _mape(vrais[masque], predits_baseline[masque])}
    return dict(sorted(resultats.items(), key=lambda kv: kv[1]["mape"], reverse=True))


def verifier_separation(app: list[dict[str, Any]], test: list[dict[str, Any]]) -> dict[str, int]:
    """Vérifie qu'aucune annonce n'est à la fois dans l'entraînement et dans le test.

    Deux contrôles : même identifiant (même ligne de la base) et même contenu (doublon exact).

    Args:
        app: Annonces d'entraînement.
        test: Annonces de test.

    Returns:
        dict[str, int]: Effectifs et nombre d'annonces communes (toujours 0 si la fonction ne lève pas d'erreur).

    Raises:
        FuiteDeDonnees: Si une annonce (ou une copie) est des deux côtés.
    """
    ids_app = {a["id"] for a in app if a.get("id") is not None}
    ids_communs = sum(1 for a in test if a.get("id") is not None and a["id"] in ids_app)
    cles_app = {_cle_doublon(a) for a in app}
    contenus_communs = sum(1 for a in test if _cle_doublon(a) in cles_app)
    if ids_communs or contenus_communs:
        raise FuiteDeDonnees(f"{ids_communs} identifiant(s) et {contenus_communs} contenu(s) communs "
                             "entre l'entraînement et le test.")
    return {"nb_entrainement": len(app), "nb_test": len(test), "identifiants_communs": 0, "contenus_communs": 0}


@dataclass
class ResultatTransaction:
    """Résultat de l'entraînement pour une transaction (location ou vente)."""

    modele: dict[str, Any]                     # contenu du fichier joblib : pipeline, nom, fourchette, confiance
    scores_test: dict[str, dict[str, float]]   # baseline / LinearRegression / RandomForestRegressor
    mape_validation_croisee: dict[str, float]
    separation: dict[str, int]
    mape_par_ville: dict[str, dict[str, float]]
    mape_par_type: dict[str, dict[str, float]]
    elagage: dict[str, Any] | None
    comparaison_avant: dict[str, Any] | None = None  # ancien modèle contre nouveau, sur le même test

    @property
    def nom_modele(self) -> str:
        """Nom du modèle retenu."""
        return self.modele["nom"]


def ajustements_demo(annonces: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Effets du meublé et de chaque équipement, appris sur les données de démonstration (IA-ANNONCE-PPT-001).

    Les annonces réelles n'indiquent ni équipements ni meublé : le modèle réel ne peut pas apprendre leur effet.
    On le reprend d'une régression linéaire sur les données de démonstration (coefficient sur log(prix) =
    effet multiplicatif). Un coefficient négatif contredit les règles des données (un équipement n'enlève pas de
    valeur) : c'est un effet faible mal appris, mis à 0 et signalé.

    Args:
        annonces: Annonces de démonstration (toutes transactions).

    Returns:
        dict: ``{transaction: {"effets": {colonne: coefficient}, "mis_a_zero": [...]}}`` ; transaction absente si
        elle a moins de ``MIN_ANNONCES`` annonces utilisables.
    """
    utilisables, _ = preparer_donnees(annonces)
    resultats: dict[str, dict[str, Any]] = {}
    for transaction in TRANSACTIONS:
        sous_ensemble = [a for a in utilisables if a["transaction"] == transaction]
        if len(sous_ensemble) < MIN_ANNONCES:
            continue
        pipeline = construire_pipeline(LinearRegression()).fit(
            vers_tableau(sous_ensemble), np.log([float(a["prix"]) for a in sous_ensemble]))
        coefficients = dict(zip(pipeline.named_steps["encodage"].get_feature_names_out(),
                                pipeline.named_steps["modele"].coef_))
        bruts = {col: float(coefficients[f"remainder__{col}"]) for col in COLONNES_AJUSTABLES}
        resultats[transaction] = {"effets": {col: max(0.0, coef) for col, coef in bruts.items()},
                                  "mis_a_zero": [col for col, coef in bruts.items() if coef < 0]}
    return resultats


def entrainer_transaction(
    annonces: list[dict[str, Any]], nb_arbres: int = NB_ARBRES, graine: int = GRAINE, nb_plis: int = NB_PLIS,
    config: dict[str, Any] | None = None, modele_avant: dict[str, Any] | None = None,
) -> ResultatTransaction:
    """Entraîne et évalue les modèles pour une transaction, puis retient le meilleur.

    Args:
        annonces: Annonces d'une seule transaction (avec leur prix), déjà contrôlées par ``preparer_donnees``.
        nb_arbres: Nombre d'arbres de la forêt complète.
        graine: Graine aléatoire.
        nb_plis: Nombre de plis de la validation croisée.
        config: Réglages enregistrés avec le modèle (``source``, ``types_equivalents``, ``ajustements``) ;
            None = données de démonstration, comportement d'origine.
        modele_avant: Modèle précédemment enregistré ; s'il est fourni, il est évalué sur EXACTEMENT les mêmes
            annonces de test que le nouveau (comparaison avant / après).

    Returns:
        ResultatTransaction: Modèle retenu (entraîné sur les 80 %) et scores.

    Raises:
        DonneesInsuffisantes: Si moins de ``MIN_ANNONCES`` annonces.
        FuiteDeDonnees: Si une annonce se retrouve à la fois dans l'entraînement et dans le test.
    """
    if len(annonces) < MIN_ANNONCES:
        raise DonneesInsuffisantes(f"{len(annonces)} annonce(s) : il en faut au moins {MIN_ANNONCES}.")
    variables = vers_tableau(annonces)
    cible = np.log(np.array([float(a["prix"]) for a in annonces]))  # on apprend log(prix), puis exp() → TND

    # Séparation 80 / 20 (graine fixe) : le jeu de test n'est utilisé qu'une fois, à la fin.
    pos_app, pos_test = train_test_split(np.arange(len(annonces)), test_size=PART_TEST, random_state=graine)
    annonces_app = [annonces[i] for i in pos_app]
    separation = verifier_separation(annonces_app, [annonces[i] for i in pos_test])
    x_app, x_test = variables.iloc[pos_app], variables.iloc[pos_test]
    y_app, y_test = cible[pos_app], cible[pos_test]
    prix_app, prix_test = np.exp(y_app), np.exp(y_test)

    # Ce que le modèle « connaît » (calculé sur l'entraînement seulement) : sert au niveau de confiance.
    villes = _noms_villes(annonces_app)
    effectifs_villes = dict(Counter(normaliser_ville(a["ville"]) for a in annonces_app))
    plages = {"surface": (float(x_app["surface"].min()), float(x_app["surface"].max())),
              "nb_pieces": (float(x_app["nb_pieces"].min()), float(x_app["nb_pieces"].max()))}
    if "nb_sdb" in x_app:
        plages["nb_sdb"] = (float(x_app["nb_sdb"].min()), float(x_app["nb_sdb"].max()))
    reglages = {"source": SOURCE_DEMO, **(config or {}), "sdb_par_defaut": _sdb_par_defaut(annonces_app)}

    def paquet(nom: str, pipeline: Pipeline, residus: np.ndarray) -> dict[str, Any]:
        """Contenu du fichier joblib d'un modèle."""
        bas, haut = np.percentile(residus, CENTILES_FOURCHETTE)
        contenu = {"pipeline": pipeline, "nom": nom, "quantiles_residus": (float(bas), float(haut)),
                   "villes": villes, "effectifs_villes": effectifs_villes, "plages": plages, **reglages}
        if reglages["source"] == SOURCE_REELLE:
            # Prix réels très dispersés : la fourchette typique (erreurs de validation croisée) dépasse déjà les
            # seuils fixés sur la démonstration. Seuil « faible » recalé sur cette largeur typique ; toute
            # estimation est au mieux « moyenne » (on le dit au lieu d'afficher une fausse « élevée »).
            typique = math.exp(float(haut)) - math.exp(float(bas))
            contenu["seuils_largeur"] = {"moyenne": 0.0,
                                         "faible": round(max(LARGEUR_FAIBLE, FACTEUR_LARGEUR_REELLE * typique), 3)}
        return contenu

    plis = KFold(n_splits=nb_plis, shuffle=True, random_state=graine)

    def evaluer(modele: Any) -> tuple[Pipeline, np.ndarray, float]:
        """Validation croisée sur les 80 % puis entraînement sur ces 80 %."""
        # Validation croisée : chaque annonce est prédite par un modèle qui ne l'a pas vue.
        predits_cv = cross_val_predict(construire_pipeline(modele), x_app, y_app, cv=plis)
        pipeline = construire_pipeline(modele).fit(x_app, y_app)
        return pipeline, y_app - predits_cv, _mape(prix_app, np.exp(predits_cv))

    candidats = _candidats(nb_arbres, graine)
    entraines: dict[str, Pipeline] = {}
    residus_cv: dict[str, np.ndarray] = {}
    mape_cv: dict[str, float] = {}
    for nom, modele in candidats.items():
        entraines[nom], residus_cv[nom], mape_cv[nom] = evaluer(modele)

    # Élagage : forêt complète contre forêt élaguée, mesurées de la même façon.
    elagage = None
    if "RandomForestRegressor" in candidats:
        exemple = annonces[pos_test[0]]
        versions = {"complete": (entraines["RandomForestRegressor"], residus_cv["RandomForestRegressor"],
                                 mape_cv["RandomForestRegressor"])}
        versions["elaguee"] = evaluer(_foret_elaguee(candidats["RandomForestRegressor"].n_estimators, graine))
        elagage = {}
        for version, (pipeline, residus, mape_v) in versions.items():
            foret = pipeline.named_steps["modele"]
            contenu = paquet("RandomForestRegressor", pipeline, residus)
            elagage[version] = {
                "parametres": {"n_estimators": foret.n_estimators, "max_depth": foret.max_depth,
                               "min_samples_leaf": foret.min_samples_leaf},
                "nb_noeuds": int(sum(arbre.tree_.node_count for arbre in foret.estimators_)),
                "taille_octets": _taille_octets(contenu),
                "temps_ms": round(_temps_median(exemple, contenu), 2),
                "mape_validation_croisee": mape_v,
                "scores_test": mesures(prix_test, np.exp(pipeline.predict(x_test))),
            }
        perte = round(versions["elaguee"][2] - versions["complete"][2], 2)
        retenue = "elaguee" if perte <= PERTE_MAX_ELAGAGE else "complete"
        elagage.update(perte_mape_validation_croisee=perte, version_retenue=retenue,
                       regle=f"version élaguée retenue si sa MAPE de validation croisée ne dépasse pas celle de la "
                             f"forêt complète de plus de {PERTE_MAX_ELAGAGE:g} point")
        entraines["RandomForestRegressor"], residus_cv["RandomForestRegressor"], mape_cv["RandomForestRegressor"] = (
            versions[retenue])

    # Mesures sur le test (une seule fois, à la fin) et choix du modèle sur la validation croisée.
    predits_baseline = baseline(x_app, prix_app, x_test)
    scores_test = {"baseline": mesures(prix_test, predits_baseline)}
    for nom, pipeline in entraines.items():
        scores_test[nom] = mesures(prix_test, np.exp(pipeline.predict(x_test)))
    meilleur = min(mape_cv, key=mape_cv.get)  # choix sur la validation croisée, jamais sur le test

    # Où le modèle retenu se trompe-t-il le plus ? (villes affichées avec leur nom habituel)
    predits_test = np.exp(entraines[meilleur].predict(x_test))
    noms = _noms_villes(annonces)

    # Avant / après : l'ancien modèle estime les MÊMES annonces de test que le nouveau.
    comparaison = None
    if modele_avant is not None:
        annonces_test = [annonces[i] for i in pos_test]
        logs_avant, _, _ = _predire_lot(modele_avant, vers_tableau(adapter_au_modele(annonces_test, modele_avant)))
        comparaison = {
            "nb_test": len(annonces_test),
            "avant": {"nom": modele_avant["nom"], "source": modele_avant.get("source", SOURCE_DEMO),
                      **mesures(prix_test, np.exp(logs_avant))},
            "apres": {"nom": meilleur, "source": reglages["source"], **scores_test[meilleur]},
            "baseline": scores_test["baseline"],
        }
    return ResultatTransaction(
        modele=paquet(meilleur, entraines[meilleur], residus_cv[meilleur]),
        scores_test=scores_test,
        mape_validation_croisee=mape_cv,
        separation=separation,
        mape_par_ville=mape_par_groupe(prix_test, predits_test, predits_baseline,
                                       [noms[v] for v in x_test["ville"]]),
        mape_par_type=mape_par_groupe(prix_test, predits_test, predits_baseline,
                                      [LIBELLES_TYPES.get(t, t) for t in x_test["type_bien"]]),
        elagage=elagage,
        comparaison_avant=comparaison,
    )


def entrainer(
    annonces: list[dict[str, Any]],
    dossier: Path,
    nb_arbres: int = NB_ARBRES,
    graine: int = GRAINE,
    nb_plis: int = NB_PLIS,
    source: dict[str, Any] | None = None,
    ajustements: dict[str, dict[str, Any]] | None = None,
    modeles_avant: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Contrôle les données, entraîne un modèle par transaction, sauvegarde modèles, métadonnées et fiche.

    Args:
        annonces: Toutes les annonces (location et vente), avec leur prix.
        dossier: Dossier de sauvegarde (``backend/modeles/``).
        nb_arbres: Nombre d'arbres de la forêt complète.
        graine: Graine aléatoire.
        nb_plis: Nombre de plis de la validation croisée.
        source: Description des données réelles importées (rapport de ``donnees_ppt.lire`` + licence) ; None =
            données de démonstration de la base.
        ajustements: Effets du meublé et des équipements repris de la démonstration (``ajustements_demo``) ;
            utilisés seulement avec des données réelles.
        modeles_avant: Modèles chargés avant l'entraînement (``charger``) pour la comparaison avant / après.

    Returns:
        dict[str, Any]: Métadonnées enregistrées (dont les scores, pour l'affichage).

    Raises:
        DonneesInsuffisantes: Si une transaction a trop peu d'annonces.
        FuiteDeDonnees: Si la séparation entraînement / test n'est pas étanche.
    """
    annonces, qualite = preparer_donnees(annonces)  # rapport de qualité AVANT tout entraînement
    dossier.mkdir(parents=True, exist_ok=True)
    reelle = source is not None
    variables = ["type_bien", "ville", "surface", "log_surface", "nb_pieces", "meuble",
                 *[f"eq_{nom}" for nom in CARACTERISTIQUES]]
    if annonces and all(a.get("nb_sdb") is not None for a in annonces):
        variables.append("nb_sdb")
    metadonnees: dict[str, Any] = {
        "source": ({"type": SOURCE_REELLE, **source} if reelle else
                   {"type": SOURCE_DEMO, "nom": "Données de démonstration générées (donnees_demo.py)"}),
        "entraine_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__, "joblib": joblib.__version__},
        "parametres": {"part_test": PART_TEST, "nb_plis": nb_plis, "nb_arbres": nb_arbres, "graine": graine,
                       "feuille_min": FEUILLE_MIN, "cible": "log(prix)",
                       "elagage": {"diviseur_arbres": DIVISEUR_ARBRES_ELAGUEE, "max_depth": PROFONDEUR_MAX_ELAGUEE,
                                   "min_samples_leaf": FEUILLE_MIN_ELAGUEE, "perte_max_mape": PERTE_MAX_ELAGAGE},
                       "confiance": {"largeur_moyenne": LARGEUR_MOYENNE, "largeur_faible": LARGEUR_FAIBLE,
                                     "ville_min_annonces": VILLE_MIN_ANNONCES}},
        "variables": variables,
        "qualite_donnees": qualite,
        "nettoyage": {"bornes_prix_m2": BORNES_PRIX_M2, "nb_exclues": qualite["aberrantes"]["nb"],
                      "exclues": [e["titre"] for e in qualite["aberrantes"]["exclues"]]},
        "transactions": {},
    }
    for transaction in TRANSACTIONS:
        sous_ensemble = [a for a in annonces if a["transaction"] == transaction]
        config = None
        effets = (ajustements or {}).get(transaction, {})
        if reelle:
            config = {"source": SOURCE_REELLE, "types_equivalents": TYPES_EQUIVALENTS_REELS,
                      "ajustements": effets.get("effets", {})}
        avant = (modeles_avant or {}).get(transaction)
        resultat = entrainer_transaction(sous_ensemble, nb_arbres, graine, nb_plis, config=config, modele_avant=avant)
        # joblib : sauvegarde des objets scikit-learn. Ne JAMAIS charger un .joblib d'origine inconnue
        # (le format pickle peut exécuter du code) : on ne charge que nos propres fichiers.
        joblib.dump(resultat.modele, dossier / f"prix_{transaction}.joblib")
        metadonnees["transactions"][transaction] = {
            "modele_retenu": resultat.nom_modele,
            "nb_annonces": len(sous_ensemble),
            "nb_entrainement": resultat.separation["nb_entrainement"],
            "nb_test": resultat.separation["nb_test"],
            "separation": resultat.separation,
            "scores_test": resultat.scores_test,
            "mape_validation_croisee": resultat.mape_validation_croisee,
            "mape_par_ville": resultat.mape_par_ville,
            "mape_par_type": resultat.mape_par_type,
            "elagage": resultat.elagage,
            "plages": resultat.modele["plages"],
            "villes": sorted(resultat.modele["villes"].values()),
            "equipements_a_effet_negatif": equipements_a_effet_negatif(resultat.modele),
            "comparaison_avant_apres": resultat.comparaison_avant,
            "ajustements_demo": ({"effets_pourcent": {col: round((math.exp(c) - 1) * 100, 1)
                                                      for col, c in effets.get("effets", {}).items()},
                                  "mis_a_zero": effets.get("mis_a_zero", [])} if reelle else None),
        }
    (dossier / FICHIER_METADONNEES).write_text(json.dumps(metadonnees, ensure_ascii=False, indent=2), encoding="utf-8")
    (dossier / FICHIER_FICHE).write_text(fiche_modele(metadonnees), encoding="utf-8")
    _cache_modeles.clear()
    _cache_positions.clear()
    return metadonnees


# --- 3. Chargement et prédiction -------------------------------------------------------------------------------

_cache_modeles: dict[str, Any] = {}
CLES_MODELE = {"pipeline", "nom", "quantiles_residus", "villes", "effectifs_villes", "plages"}


def charger(dossier: Path) -> dict[str, Any]:
    """Charge les modèles une seule fois (mise en cache), rechargés si un nouvel entraînement a eu lieu.

    Args:
        dossier: Dossier des modèles.

    Returns:
        dict[str, Any]: ``{"metadonnees": ..., "location": {...}, "vente": {...}}``.

    Raises:
        ModeleIndisponible: Si les fichiers sont absents, illisibles ou d'une version précédente du code.
    """
    chemin_meta = dossier / FICHIER_METADONNEES
    if not chemin_meta.exists():
        raise ModeleIndisponible("Le modèle d'estimation du prix n'a pas encore été entraîné.")
    cle = f"{chemin_meta}:{chemin_meta.stat().st_mtime_ns}"
    if _cache_modeles.get("cle") != cle:
        try:
            charges = {"metadonnees": json.loads(chemin_meta.read_text(encoding="utf-8"))}
            for transaction in TRANSACTIONS:
                charges[transaction] = joblib.load(dossier / f"prix_{transaction}.joblib")
        except Exception as erreur:  # fichier manquant, corrompu ou d'une version incompatible
            raise ModeleIndisponible("Le modèle d'estimation du prix ne peut pas être chargé.") from erreur
        if any(not CLES_MODELE <= set(charges[t]) for t in TRANSACTIONS):
            # Modèle entraîné par une version précédente (sans plages ni effectifs) : il faut réentraîner.
            raise ModeleIndisponible("Le modèle d'estimation du prix doit être réentraîné.")
        _cache_modeles.clear()
        _cache_modeles.update(cle=cle, modeles=charges)
    return _cache_modeles["modeles"]


def _arrondir(prix: float, transaction: str) -> int:
    """Arrondi lisible : à 10 TND pour un loyer, à 1 000 TND pour une vente."""
    pas = 10 if transaction == "location" else 1000
    return int(max(pas, round(prix / pas) * pas))


def _predire_lot(modele: dict[str, Any], tableau: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Estimation et fourchette (en log) de plusieurs annonces en un seul passage.

    Forêt aléatoire : chaque arbre donne sa propre estimation ; la prédiction de la forêt est leur moyenne, la
    fourchette va du 10e au 90e centile (si les arbres sont d'accord, elle est étroite). Autre modèle : on ajoute
    les erreurs typiques (10e et 90e centiles) mesurées pendant la validation croisée.

    Args:
        modele: Modèle chargé (pipeline, nom, quantiles des résidus).
        tableau: Variables des annonces.

    Returns:
        tuple: (estimations, bornes basses, bornes hautes), en log(prix).
    """
    pipeline = modele["pipeline"]
    if modele["nom"] == "RandomForestRegressor":
        x = pipeline.named_steps["encodage"].transform(tableau)
        par_arbre = np.stack([arbre.predict(x) for arbre in pipeline.named_steps["modele"].estimators_])
        logs = par_arbre.mean(axis=0)  # exactement ce que fait RandomForestRegressor.predict
        bas, haut = np.percentile(par_arbre, CENTILES_FOURCHETTE, axis=0)
    else:
        logs = pipeline.predict(tableau)
        bas, haut = logs + modele["quantiles_residus"][0], logs + modele["quantiles_residus"][1]
    # Modèle réel : le meublé et les équipements n'ont pas pu être appris (absents des annonces réelles) ; on
    # ajoute leurs effets repris de la démonstration (en log : un effet multiplicatif devient une addition).
    ajustements = modele.get("ajustements") or {}
    if ajustements:
        decalage = sum(coef * tableau[col].to_numpy() for col, coef in ajustements.items())
        logs, bas, haut = logs + decalage, bas + decalage, haut + decalage
    return logs, np.minimum(bas, logs), np.maximum(haut, logs)


def _confiance(donnees: dict[str, Any], modele: dict[str, Any], estime: float, bas: float, haut: float) -> dict[str, Any]:
    """Niveau de confiance d'une estimation et ses raisons.

    Un modèle répond toujours, même quand il ne sait pas (c'est une forme d'« hallucination ») : pour une ville
    jamais vue, il calcule une ville « moyenne » ; pour 2 000 m², il prolonge une tendance apprise entre 20 et
    300 m². On le signale au lieu de le cacher.
    - faible : ville absente de l'entraînement, surface ou nombre de pièces hors de la plage vue, ou fourchette
      plus large que ``LARGEUR_FAIBLE`` × prix estimé ;
    - moyenne : ville vue moins de ``VILLE_MIN_ANNONCES`` fois, ou fourchette plus large que ``LARGEUR_MOYENNE`` ;
    - élevée : sinon.

    Args:
        donnees: Annonce estimée.
        modele: Modèle chargé (villes, effectifs, plages).
        estime: Prix estimé (TND).
        bas: Bas de la fourchette (TND).
        haut: Haut de la fourchette (TND).

    Returns:
        dict[str, Any]: ``{"niveau": "élevée" | "moyenne" | "faible", "raisons": [...]}``.
    """
    faibles: list[str] = []
    moyennes: list[str] = []
    cle = normaliser_ville(donnees["ville"])
    if cle not in modele["villes"]:
        faibles.append(f"Ville « {' '.join(str(donnees['ville']).split())} » absente des données d'entraînement")
    elif modele["effectifs_villes"].get(cle, 0) < VILLE_MIN_ANNONCES:
        moyennes.append(f"Ville « {modele['villes'][cle]} » peu représentée "
                        f"({modele['effectifs_villes'].get(cle, 0)} annonce(s) d'entraînement)")
    equivalent = (modele.get("types_equivalents") or {}).get(donnees["type_bien"])
    if equivalent:
        moyennes.append(f"Type « {LIBELLES_TYPES[donnees['type_bien']]} » estimé comme « {LIBELLES_TYPES[equivalent]} » "
                        "(les annonces réelles ne distinguent pas ces deux types)")
    for champ, libelle, unite in (("surface", "Surface de {:g} m²", " m²"), ("nb_pieces", "{:g} pièce(s)", ""),
                                  ("nb_sdb", "{:g} salle(s) de bain", "")):
        if champ not in modele["plages"] or donnees.get(champ) is None:
            continue  # salles de bain : facultatives, et inconnues des modèles de démonstration
        mini, maxi = modele["plages"][champ]
        valeur = float(donnees[champ])
        if not mini <= valeur <= maxi:
            sens = "au-delà de" if valeur > maxi else "en deçà de"
            faibles.append(f"{libelle.format(valeur)} {sens} la plage connue ({mini:g}–{maxi:g}{unite})")
    largeur = (haut - bas) / estime
    seuils = modele.get("seuils_largeur") or {"moyenne": LARGEUR_MOYENNE, "faible": LARGEUR_FAIBLE}
    if largeur > seuils["faible"]:
        faibles.append(f"Fourchette très large : {round(largeur * 100)} % du prix estimé")
    elif largeur > seuils["moyenne"]:
        moyennes.append(f"Fourchette assez large : {round(largeur * 100)} % du prix estimé"
                        + (" (les prix affichés varient beaucoup entre biens comparables)"
                           if modele.get("source") == SOURCE_REELLE else ""))
    if faibles:
        return {"niveau": "faible", "raisons": faibles + moyennes}
    if moyennes:
        return {"niveau": "moyenne", "raisons": moyennes}
    return {"niveau": "élevée", "raisons": ["Bien comparable aux annonces d'entraînement : ville connue, surface "
                                            "et nombre de pièces dans la plage apprise, fourchette resserrée"]}


def _variantes(donnees: dict[str, Any], villes: dict[str, str]) -> list[tuple[str, str | None, dict[str, Any]]]:
    """Annonces « modifiées » pour mesurer l'effet de chaque caractéristique (simulation avec / sans).

    Chaque variante est (groupe, libellé, annonce modifiée) :
    - meublé / non meublé ; chaque équipement présent ou absent : on bascule la valeur ;
    - ville et type de bien : on remplace par chacune des autres valeurs (on comparera à leur moyenne).

    Args:
        donnees: Annonce à estimer.
        villes: Villes connues du modèle (clé normalisée → nom affiché).

    Returns:
        list: Variantes.
    """
    variantes = [("meuble", "Meublé" if donnees["meuble"] else "Non meublé", {**donnees, "meuble": not donnees["meuble"]})]
    presents = set(donnees.get("caracteristiques") or [])
    for nom in CARACTERISTIQUES:
        libelle = LIBELLES_CARACTERISTIQUES[nom] if nom in presents else f"Sans {LIBELLES_CARACTERISTIQUES[nom].lower()}"
        bascule = sorted(presents - {nom}) if nom in presents else sorted(presents | {nom})
        variantes.append((f"eq_{nom}", libelle, {**donnees, "caracteristiques": bascule}))
    salles = donnees.get("nb_sdb")
    if salles is not None:  # effet d'une salle de bain de plus ou de moins
        variantes.append(("nb_sdb", f"{salles} salle(s) de bain",
                          {**donnees, "nb_sdb": salles - 1 if salles > 1 else salles + 1}))
    cle_ville = normaliser_ville(donnees["ville"])
    if cle_ville in villes:
        for autre in villes:
            if autre != cle_ville:
                variantes.append(("ville", None, {**donnees, "ville": autre}))
    for autre in LIBELLES_TYPES:
        if autre != donnees["type_bien"]:
            variantes.append(("type", None, {**donnees, "type_bien": autre}))
    return variantes


def estimer_avec_modele(donnees: dict[str, Any], modele: dict[str, Any], infos_modele: dict[str, Any]) -> dict[str, Any]:
    """Estimation complète avec un modèle déjà chargé (prix, fourchette, confiance, facteurs, avertissement).

    Toutes les variantes (simulation avec / sans) sont prédites en UN seul appel au modèle : c'est ce qui garde
    le temps de réponse sous 300 ms.

    Args:
        donnees: type_bien, transaction, ville, surface, nb_pieces, meuble, caracteristiques.
        modele: Contenu du fichier joblib de la transaction.
        infos_modele: ``nom``, ``mape_test`` et ``entraine_le`` (affichés au propriétaire).

    Returns:
        dict[str, Any]: Réponse de ``POST /api/ia/estimation-prix``.
    """
    transaction = donnees["transaction"]
    villes = modele["villes"]
    variantes = _variantes(donnees, villes)
    tableau = vers_tableau(adapter_au_modele([donnees] + [v[2] for v in variantes], modele))
    logs, bas, haut = _predire_lot(modele, tableau)  # une seule prédiction groupée
    log_estime = float(logs[0])
    prix_estime = math.exp(log_estime)
    ajustements = modele.get("ajustements") or {}

    # Effet d'une caractéristique = écart entre le prix de l'annonce et le prix « sans » (ou « avec ») elle.
    facteurs = []
    for (groupe, libelle, _annonce), log_variante in zip(variantes, logs[1:]):
        if groupe in ("ville", "type"):
            continue
        if groupe in ajustements:  # effet non appris sur les annonces réelles : on le dit
            libelle += MENTION_AJUSTEMENT
        facteurs.append({"libelle": libelle, "effet_pourcent": round((math.exp(log_estime - log_variante) - 1) * 100)})
    # Ville et type : comparés à la moyenne des autres villes / des autres types.
    for groupe, libelle in (("ville", f"Ville : {villes.get(normaliser_ville(donnees['ville']), donnees['ville'])}"),
                            ("type", f"Type : {LIBELLES_TYPES[donnees['type_bien']]}")):
        autres = [lv for (g, _l, _a), lv in zip(variantes, logs[1:]) if g == groupe]
        if autres:
            effet = math.exp(log_estime - float(np.mean(autres))) - 1
            facteurs.append({"libelle": libelle, "effet_pourcent": round(effet * 100)})
    facteurs = [f for f in facteurs if abs(f["effet_pourcent"]) >= EFFET_MIN_POURCENT]
    facteurs.sort(key=lambda f: abs(f["effet_pourcent"]), reverse=True)

    bas_tnd, haut_tnd = math.exp(float(bas[0])), math.exp(float(haut[0]))
    confiance = _confiance(donnees, modele, prix_estime, bas_tnd, haut_tnd)
    base = AVERTISSEMENT_REEL if modele.get("source") == SOURCE_REELLE else AVERTISSEMENT
    avertissement = base if confiance["niveau"] != "faible" else f"{AVERTISSEMENT_FAIBLE} {base}"
    return {
        "prix_estime": _arrondir(prix_estime, transaction),
        "fourchette": {"min": _arrondir(bas_tnd, transaction), "max": _arrondir(haut_tnd, transaction)},
        "devise": "TND",
        "transaction": transaction,
        "confiance": confiance,
        "facteurs": facteurs[:NB_FACTEURS],
        "modele": infos_modele,
        "avertissement": avertissement,
    }


def estimer(donnees: dict[str, Any], dossier: Path) -> dict[str, Any]:
    """Estime le prix d'une annonce avec les modèles enregistrés dans ``dossier``.

    Args:
        donnees: type_bien, transaction, ville, surface, nb_pieces, meuble, caracteristiques.
        dossier: Dossier des modèles.

    Returns:
        dict[str, Any]: Réponse de ``POST /api/ia/estimation-prix``.

    Raises:
        ModeleIndisponible: Si le modèle n'est pas entraîné.
    """
    modeles = charger(dossier)
    transaction = donnees["transaction"]
    modele = modeles[transaction]
    meta = modeles["metadonnees"]
    return estimer_avec_modele(donnees, modele, {
        "nom": modele["nom"],
        "mape_test": meta["transactions"][transaction]["scores_test"][modele["nom"]]["mape"],
        "entraine_le": meta["entraine_le"][:10],
        "source": modele.get("source", SOURCE_DEMO),
    })


def _temps_moyen(donnees: dict[str, Any], modele: dict[str, Any], repetitions: int = 30) -> float:
    """Temps moyen (ms) d'une estimation complète avec un modèle en mémoire (premier appel non compté)."""
    infos = {"nom": modele["nom"], "mape_test": 0.0, "entraine_le": ""}
    estimer_avec_modele(donnees, modele, infos)
    debut = time.perf_counter()
    for _ in range(repetitions):
        estimer_avec_modele(donnees, modele, infos)
    return (time.perf_counter() - debut) / repetitions * 1000


def _temps_median(donnees: dict[str, Any], modele: dict[str, Any], series: int = 5, repetitions: int = 10) -> float:
    """Temps (ms) d'une estimation : médiane de plusieurs séries.

    Une seule série est trop sensible à la charge de la machine (mesures observées du simple au triple d'une
    exécution à l'autre) ; la médiane de 5 séries est stable à quelques millisecondes près.
    """
    return statistics.median(_temps_moyen(donnees, modele, repetitions) for _ in range(series))


def equipements_a_effet_negatif(modele: dict[str, Any]) -> list[str]:
    """Équipements dont l'AJOUT fait baisser le prix estimé (coefficient négatif d'une régression linéaire).

    Les règles des données disent le contraire (chaque équipement augmente le prix) : un coefficient négatif est
    donc un effet mal appris (trop peu d'annonces pour un effet faible). Contrôle refait à chaque entraînement
    et signalé dans la fiche du modèle. Pour une forêt, il n'y a pas de coefficient : liste vide.

    Args:
        modele: Contenu du fichier joblib.

    Returns:
        list[str]: Noms des équipements concernés.
    """
    if modele["nom"] != "LinearRegression":
        return []
    pipeline = modele["pipeline"]
    noms = pipeline.named_steps["encodage"].get_feature_names_out()
    coefficients = dict(zip(noms, pipeline.named_steps["modele"].coef_))
    return [nom for nom in CARACTERISTIQUES if coefficients[f"remainder__eq_{nom}"] < 0]


def villes_connues(dossier: Path) -> list[dict[str, Any]]:
    """Villes connues du modèle (location et vente réunies), pour la liste déroulante du champ « Ville ».

    Choisir une ville de cette liste évite la confiance « faible » due à une ville absente de l'entraînement.
    Liste vide si le modèle n'est pas entraîné (la saisie libre reste possible).

    Args:
        dossier: Dossier des modèles.

    Returns:
        list[dict[str, Any]]: ``[{"nom": ..., "nb_annonces": ...}]`` triée par nom (accents ignorés).
    """
    try:
        modeles = charger(dossier)
    except ModeleIndisponible:
        return []
    effectifs: Counter[str] = Counter()
    noms: dict[str, str] = {}
    for transaction in TRANSACTIONS:
        modele = modeles[transaction]
        for cle, nom in modele["villes"].items():
            noms.setdefault(cle, nom)
            effectifs[cle] += modele["effectifs_villes"].get(cle, 0)
    return [{"nom": noms[cle], "nb_annonces": effectifs[cle]} for cle in sorted(noms)]


def mesurer_temps_estimation(donnees: dict[str, Any], dossier: Path, repetitions: int = 50) -> float:
    """Temps moyen d'une estimation (modèle déjà chargé), en millisecondes.

    Args:
        donnees: Annonce à estimer.
        dossier: Dossier des modèles.
        repetitions: Nombre de mesures.

    Returns:
        float: Durée moyenne en ms.
    """
    estimer(donnees, dossier)  # premier appel : chargement des fichiers, non compté
    debut = time.perf_counter()
    for _ in range(repetitions):
        estimer(donnees, dossier)
    return (time.perf_counter() - debut) / repetitions * 1000


# --- 4. Badge « bonne affaire » prudent (cartes et fiche publiques) --------------------------------------------

_cache_positions: dict[tuple[Any, ...], dict[str, Any] | None] = {}
TAILLE_MAX_CACHE = 5000


def _position(prix: float, estime: float, bas: float, haut: float) -> dict[str, Any]:
    """Compare le prix affiché à la FOURCHETTE estimée (et non au seul prix estimé).

    Prudence : un prix un peu sous l'estimation reste dans l'incertitude du modèle. On ne parle de « bonne
    affaire » que sous le bas de la fourchette, et de prix élevé qu'au-dessus du haut.

    Args:
        prix: Prix de l'annonce.
        estime: Prix estimé par le modèle.
        bas: Bas de la fourchette.
        haut: Haut de la fourchette.

    Returns:
        dict[str, Any]: ``position`` (sous / dans / au_dessus), ``libelle`` et ``ecart_pourcent`` (vs estimation).
    """
    ecart = round((prix / estime - 1) * 100)
    if prix < bas:
        return {"position": "sous", "libelle": "Bonne affaire", "ecart_pourcent": ecart}
    if prix > haut:
        return {"position": "au_dessus", "libelle": "Prix au-dessus du marché", "ecart_pourcent": ecart}
    return {"position": "dans", "libelle": "Prix dans le marché", "ecart_pourcent": ecart}


def positions_marche(annonces: list[dict[str, Any]], dossier: Path) -> dict[int, dict[str, Any]]:
    """Position de chaque annonce par rapport au marché estimé, avec mise en cache.

    Pas de badge (rien dans le résultat) si le modèle est absent ou si la confiance est faible : mieux vaut ne
    rien afficher qu'afficher « Bonne affaire » sur une estimation qui extrapole.

    Le cache est indexé par (annonce, date de modification, version du modèle) : une annonce modifiée ou un
    nouveau modèle déclenchent un nouveau calcul. Les annonces manquantes sont prédites en un seul appel par
    transaction.

    Args:
        annonces: Annonces sérialisées (``Annonce.to_dict()``).
        dossier: Dossier des modèles.

    Returns:
        dict[int, dict[str, Any]]: Position par identifiant d'annonce.
    """
    try:
        modeles = charger(dossier)
    except ModeleIndisponible:
        return {}
    # Version du modèle = dossier + date d'entraînement : un nouvel entraînement invalide tout le cache.
    version = f"{dossier}|{modeles['metadonnees']['entraine_le']}"
    if len(_cache_positions) > TAILLE_MAX_CACHE:
        _cache_positions.clear()
    resultats: dict[int, dict[str, Any]] = {}
    a_calculer: dict[str, list[dict[str, Any]]] = {t: [] for t in TRANSACTIONS}
    for annonce in annonces:
        cle = (annonce["id"], annonce.get("updated_at"), version)
        if cle in _cache_positions:
            if _cache_positions[cle] is not None:
                resultats[annonce["id"]] = _cache_positions[cle]
        elif annonce.get("transaction") in a_calculer:
            a_calculer[annonce["transaction"]].append(annonce)
    for transaction, groupe in a_calculer.items():
        if not groupe:
            continue
        modele = modeles[transaction]
        logs, bas, haut = _predire_lot(modele, vers_tableau(adapter_au_modele(groupe, modele)))
        for annonce, log_estime, log_bas, log_haut in zip(groupe, logs, bas, haut):
            estime, borne_basse, borne_haute = (math.exp(float(v)) for v in (log_estime, log_bas, log_haut))
            confiance = _confiance(annonce, modele, estime, borne_basse, borne_haute)
            position = (None if confiance["niveau"] == "faible"
                        else _position(float(annonce["prix"]), estime, borne_basse, borne_haute))
            _cache_positions[(annonce["id"], annonce.get("updated_at"), version)] = position
            if position is not None:
                resultats[annonce["id"]] = position
    return resultats


# --- 5. Fiche du modèle (model card) ---------------------------------------------------------------------------

def _tableau_md(entetes: list[str], lignes: list[list[Any]]) -> str:
    """Tableau Markdown."""
    sortie = ["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
    sortie += ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes]
    return "\n".join(sortie)


def _nombre(valeur: float, decimales: int = 0) -> str:
    """Nombre lisible à la française (espace pour les milliers, virgule décimale)."""
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


def fiche_modele(meta: dict[str, Any]) -> str:
    """Fiche du modèle (« model card ») : ce qu'il faut savoir avant d'utiliser ce modèle.

    Args:
        meta: Métadonnées de l'entraînement.

    Returns:
        str: Contenu Markdown de ``FICHE_MODELE.md``.
    """
    qualite = meta["qualite_donnees"]
    p = meta["parametres"]
    source = meta.get("source") or {"type": SOURCE_DEMO}
    reelle = source["type"] == SOURCE_REELLE
    lignes = [
        "# Fiche du modèle — Estimation indicative du prix des annonces",
        "",
        f"Générée automatiquement par `flask --app run entrainer-prix` le {meta['entraine_le']} (UTC). "
        "Ne pas modifier à la main : elle est réécrite à chaque entraînement.",
        "",
    ]
    if reelle:
        lignes += [
            f"> **À lire d'abord.** Ce modèle est entraîné sur des **annonces réelles** (« {source['nom']} », fichier "
            f"`{source['fichier']}`). Ce sont des **prix affichés** dans des annonces en ligne, pas des prix de vente "
            "conclus. **Licence du jeu de données : " + str(source.get("licence", "non vérifiée")) + ".** Le meublé "
            "et les équipements sont absents de ces annonces : leurs effets sont repris des données de démonstration.",
            "",
            "## Source des données",
            "",
            f"- Fichier : `{source['fichier']}` (SHA-256 `{source['sha256']}`), {source['nb_lignes']} lignes ; "
            f"annonces importées : {source['nb_annonces_importees']} ; écartées à l'import : {source['ecartees']}.",
            *[f"- Règle d'import : {regle}." for regle in source["regles"]],
            "- Confiance (données réelles) : au mieux « moyenne », car les prix affichés varient beaucoup entre biens "
            f"comparables ; « faible » si la fourchette dépasse {_nombre(FACTEUR_LARGEUR_REELLE, 2)} × la largeur "
            "typique mesurée en validation croisée, ou dans les cas d'extrapolation ci-dessous.",
            "",
        ]
    else:
        lignes += [
            "> **À lire d'abord.** Ce modèle est entraîné sur des **données de démonstration générées par des "
            "règles** (`backend/app/ia/donnees_demo.py`). Ses scores mesurent sa capacité à retrouver ces règles ; ils "
            "ne mesurent **pas** la précision d'une estimation sur le marché immobilier réel tunisien.",
            "",
        ]
    lignes += [
        "## Données et provenance",
        "",
        f"- Annonces lues : {qualite['nb_annonces_lues']} ; utilisables après contrôle : "
        f"{qualite['nb_annonces_utilisables']}.",
        (f"- Provenance : {qualite['provenance']['autres']} annonce(s) réelle(s) importée(s) du fichier ci-dessus."
         if reelle else
         f"- Provenance : {qualite['provenance']['demonstration_generee']} annonce(s) de démonstration générée(s) "
         f"(titre « [DÉMO] »), {qualite['provenance']['autres']} autre(s) annonce(s) de la base (saisies de test, non "
         "vérifiées)."),
        f"- Valeurs manquantes (variables et prix) : {qualite['valeurs_manquantes']} ; annonces incomplètes exclues : "
        f"{qualite['nb_incompletes_exclues']}.",
        f"- Prix aberrants exclus : {qualite['aberrantes']['nb']} (règle : {qualite['aberrantes']['regle']}).",
    ]
    exclues = qualite["aberrantes"]["exclues"]
    lignes += [f"  - {e['titre']} ({e['transaction']}, {_nombre(e['prix_m2'], 2)} TND/m²)"
               for e in exclues[:MAX_EXCLUES_AFFICHEES]]
    if len(exclues) > MAX_EXCLUES_AFFICHEES:
        lignes.append(f"  - … et {len(exclues) - MAX_EXCLUES_AFFICHEES} autre(s) (liste complète dans "
                      f"`{FICHIER_METADONNEES}`)")
    lignes += [
        f"- Doublons exacts exclus : {qualite['doublons']['nb']} ({qualite['doublons']['regle']}).",
        f"- Par transaction : {qualite['par_transaction']}",
        f"- Par ville : {qualite['par_ville']}",
        f"- Par type : {qualite['par_type']}",
        "",
        "## Méthode",
        "",
        f"- Variables : {', '.join(meta['variables'])}. Cible : {p['cible']}. Un modèle pour la location, un pour la "
        "vente.",
        f"- Séparation {round((1 - p['part_test']) * 100)} % entraînement / {round(p['part_test'] * 100)} % test, "
        f"graine {p['graine']} ; aucune annonce commune entre entraînement et test (vérifié à chaque entraînement).",
        f"- Choix du modèle : plus faible MAPE en validation croisée ({p['nb_plis']} plis) sur l'entraînement, "
        "jamais sur le test. Baseline : prix médian au m² de la ville × surface.",
        "- Fourchette : 10e–90e centiles des arbres (forêt) ou des erreurs de validation croisée (régression "
        "linéaire).",
        f"- Confiance : faible si ville absente de l'entraînement, surface ou nombre de pièces hors de la plage vue, "
        f"ou fourchette > {round(p['confiance']['largeur_faible'] * 100)} % du prix ; moyenne si ville vue moins de "
        f"{p['confiance']['ville_min_annonces']} fois ou fourchette > {round(p['confiance']['largeur_moyenne'] * 100)} "
        "% ; élevée sinon. Pas de badge public en confiance faible.",
        "",
    ]
    for transaction, infos in meta["transactions"].items():
        lignes += [
            f"## Résultats — {transaction} ({infos['nb_annonces']} annonces : {infos['nb_entrainement']} "
            f"entraînement / {infos['nb_test']} test)",
            "",
            f"Modèle retenu : **{infos['modele_retenu']}**. Plage connue : surface {infos['plages']['surface'][0]:g}–"
            f"{infos['plages']['surface'][1]:g} m², pièces {infos['plages']['nb_pieces'][0]:g}–"
            f"{infos['plages']['nb_pieces'][1]:g}.",
            "",
            ("**Effet à contre-sens détecté** : l'ajout de " + ", ".join(infos["equipements_a_effet_negatif"])
             + " fait BAISSER le prix estimé, alors que les règles des données l'augmentent (effet faible mal appris)."
             if infos.get("equipements_a_effet_negatif")
             else "Contrôle des équipements : aucun équipement ne fait baisser le prix estimé."),
            "",
            _tableau_md(["Modèle", "MAE test (TND)", "MAPE test (%)", "R² test", "MAPE val. croisée (%)"], [
                [nom + (" (retenu)" if nom == infos["modele_retenu"] else ""), _nombre(s["mae"]),
                 _nombre(s["mape"], 1), _nombre(s["r2"], 3),
                 _nombre(infos["mape_validation_croisee"][nom], 1) if nom in infos["mape_validation_croisee"] else "—"]
                for nom, s in infos["scores_test"].items()]),
            "",
            "Erreur du modèle retenu par ville et par type (test ; peu d'annonces par groupe : ordre de grandeur "
            "seulement) :",
            "",
            _tableau_md(["Ville", "n test", "MAPE modèle (%)", "MAPE baseline (%)"],
                        [[g, v["n"], _nombre(v["mape"], 1), _nombre(v["mape_baseline"], 1)]
                         for g, v in infos["mape_par_ville"].items()]),
            "",
            _tableau_md(["Type", "n test", "MAPE modèle (%)", "MAPE baseline (%)"],
                        [[g, v["n"], _nombre(v["mape"], 1), _nombre(v["mape_baseline"], 1)]
                         for g, v in infos["mape_par_type"].items()]),
            "",
        ]
        elagage = infos.get("elagage")
        if elagage:
            lignes += [
                "Élagage de la forêt aléatoire :",
                "",
                _tableau_md(["Version", "Paramètres", "Nœuds", "Fichier joblib", "Temps d'une estimation (médiane)",
                             "MAPE val. croisée (%)", "MAPE test (%)"], [
                    [version + (" (retenue)" if version == elagage["version_retenue"] else ""),
                     ", ".join(f"{k}={v}" for k, v in elagage[version]["parametres"].items()),
                     _nombre(elagage[version]["nb_noeuds"]), f"{_nombre(elagage[version]['taille_octets'] / 1024, 1)} Ko",
                     f"{_nombre(elagage[version]['temps_ms'], 1)} ms",
                     _nombre(elagage[version]["mape_validation_croisee"], 1),
                     _nombre(elagage[version]["scores_test"]["mape"], 1)]
                    for version in ("complete", "elaguee")]),
                "",
                f"Règle : {elagage['regle']} ; écart mesuré : {_nombre(elagage['perte_mape_validation_croisee'], 2)} "
                "point(s).",
                "",
            ]
        comparaison = infos.get("comparaison_avant_apres")
        if comparaison:
            lignes += [
                f"Comparaison avant / après sur les **mêmes {comparaison['nb_test']} annonces de test** :",
                "",
                _tableau_md(["", "Modèle (source)", "MAE (TND)", "MAPE (%)", "R²"], [
                    [etape, f"{c['nom']} ({c.get('source', 'baseline')})" if "nom" in c else "baseline",
                     _nombre(c["mae"]), _nombre(c["mape"], 1), _nombre(c["r2"], 3)]
                    for etape, c in (("avant", comparaison["avant"]), ("après", comparaison["apres"]),
                                     ("baseline", comparaison["baseline"]))]),
                "",
            ]
        ajust = infos.get("ajustements_demo")
        if ajust:
            lignes += [
                "Effets repris des données de démonstration (non appris sur les annonces réelles) : "
                + ", ".join(f"{col} {_nombre(v, 1)} %" for col, v in ajust["effets_pourcent"].items())
                + (f" ; mis à 0 car de signe contraire aux règles : {', '.join(ajust['mis_a_zero'])}"
                   if ajust["mis_a_zero"] else "") + ".",
                "",
            ]
    if reelle:
        lignes += [
            "## Limites connues",
            "",
            "- Prix affichés dans des annonces en ligne, pas prix de transaction : le modèle apprend ce que les "
            "vendeurs et bailleurs demandent.",
            "- Le meublé et les équipements ne sont pas dans les données réelles : leurs effets viennent de la "
            "démonstration (ordre de grandeur, pas une mesure du marché).",
            "- Maison et villa, studio, résidence et appartement ne sont pas distingués dans les données réelles : "
            "studio et résidence sont estimés comme des appartements, une villa comme une maison (confiance moyenne).",
            "- L'état du bien, l'étage, la vue ou l'année de construction ne sont pas connus : erreur irréductible.",
            "- Prix aberrants et annonces mal classées (loyer à la nuit, vente classée en location) : une partie est "
            "écartée par des règles simples, pas toutes.",
            "- Villes peu représentées : MAPE par ville à lire comme des tendances ; ville inconnue = confiance faible.",
            "- Licence du jeu de données : voir l'encadré en tête de fiche ; à vérifier avant toute diffusion.",
            "",
        ]
    else:
        lignes += [
            "## Limites connues",
            "",
            "- Données générées : le modèle apprend les règles du générateur (prix au m² par ville, coefficients par "
            "type, équipements, meublé) et leur bruit ; il ne connaît rien du marché réel.",
            "- L'état du bien (neuf, à rafraîchir) influence le prix généré mais n'est pas une variable : erreur "
            "irréductible.",
            "- Les petits effets (balcon, internet, chauffage…) sont mal appris avec si peu d'annonces : leur signe peut "
            "s'inverser. Les effets forts (ville, surface, piscine, meublé en location) sont plus stables.",
            "- MAPE par ville et par type calculées sur très peu d'annonces de test : à lire comme des tendances.",
            "- Hors de la plage apprise (ville inconnue, surface ou pièces extrêmes), le modèle extrapole : la "
            "confiance est alors « faible » et aucun badge n'est affiché.",
            "- Le badge des annonces ayant servi à l'entraînement est optimiste (le modèle les a déjà vues).",
            "",
        ]
    lignes += [
        "## Usage prévu",
        "",
        "- Aider un propriétaire à situer son prix au moment de rédiger l'annonce (bouton « Estimer le prix ») ; le "
        "propriétaire reste libre de son prix.",
        "- Afficher, sur le site de démonstration, un badge prudent « Bonne affaire / dans le marché / au-dessus du "
        "marché » accompagné de la mention « Estimation indicative ».",
        "",
        "## Usage déconseillé",
        "",
        "- Fixer automatiquement un prix, évaluer un bien pour un prêt, une vente, une succession ou un litige.",
        ("- Présenter ces scores comme une garantie : ils sont mesurés sur des prix affichés, avec les limites "
         "ci-dessus." if reelle else
         "- Présenter ces scores comme une mesure de la précision sur le marché immobilier réel."),
        "- Estimer des biens hors de la plage apprise (villes absentes, surfaces extrêmes) sans contrôle humain.",
        "",
        "## Versions",
        "",
        ", ".join(f"{nom} {version}" for nom, version in meta["versions"].items()),
        "",
    ]
    return "\n".join(lignes)
