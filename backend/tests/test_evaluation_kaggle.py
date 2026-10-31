"""Tests de l'évaluation sur données Kaggle (IA-ANNONCE-002-KAGGLE).

Les tests n'utilisent PAS le vrai fichier téléchargé : un petit jeu au même format est généré ici (graine fixe),
avec les défauts rencontrés dans les vraies données (ville vide, pièces manquantes, doublon, prix aberrant).
"""

from __future__ import annotations

import json
import math
import random
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from app.ia import estimation_prix, evaluation_kaggle

GOUVERNORATS = {"Tunis": 3000, "Ariana": 2500, "Nabeul": 1800, "Sousse": 2000, "Sfax": 1500}
AGES = ["0", "1-5 ", "5-10 ", "10-20 ", "Plus de 100 ", None]


def ligne_kaggle(identifiant: int, alea: random.Random) -> dict:
    """Une vente au format de train.csv : prix = surface × prix au m² du gouvernorat × équipements × bruit."""
    gouvernorat = alea.choice(list(GOUVERNORATS))
    surface = alea.randint(60, 400)
    piscine, ascenseur = alea.random() < 0.3, alea.random() < 0.4
    chambres = max(1, surface // 50)
    prix = surface * GOUVERNORATS[gouvernorat] * (1.15 if piscine else 1) * (1 + 0.04 * chambres)
    prix *= math.exp(alea.gauss(0, 0.1))
    return {
        "price_tnd": round(prix, -3), "location": "Quartier", "city": alea.choice([gouvernorat, None]),
        "governorate": gouvernorat, "Area": surface, "pieces": chambres + 1, "room": chambres,
        "bathroom": alea.choice([1, 2, None]), "age": alea.choice(AGES), "state": alea.choice([0, 1, 2, None]),
        "latt": 36.8, "long": 10.2, "distance_to_capital": alea.uniform(0, 300), "garage": int(alea.random() < 0.5),
        "garden": 0, "concierge": 0, "beach_view": 0, "mountain_view": 0, "pool": int(piscine),
        "elevator": int(ascenseur), "furnished": 0, "equipped_kitchen": 1, "central_heating": 0,
        "air_conditioning": 1, "Id": identifiant,
    }


@pytest.fixture
def jeu_kaggle(tmp_path) -> Path:
    """Archive .zip contenant un train.csv synthétique de 260 lignes + défauts réels."""
    alea = random.Random(11)
    lignes = [ligne_kaggle(i, alea) for i in range(1, 261)]
    lignes.append({**lignes[0], "Id": 900})                                  # doublon exact (Id différent)
    lignes.append({**lignes[1], "Id": 901, "pieces": None})                  # pièces manquantes
    lignes.append({**lignes[2], "Id": 902, "price_tnd": 500.0})              # 500 TND la maison : aberrant
    archive = tmp_path / "tunisian-house-prices-prediction.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("train.csv", pd.DataFrame(lignes).to_csv(index=False))
        z.writestr("test.csv", "Id\n1\n")
    return archive


@pytest.fixture
def classement(tmp_path) -> Path:
    """Classement au format Kaggle, avec des noms et pseudonymes qui ne doivent jamais être recopiés."""
    chemin = tmp_path / "classement.csv"
    chemin.write_text(
        "﻿Rank,TeamId,TeamName,LastSubmissionDate,Score,SubmissionCount,TeamMemberUserNames\n"
        '2,22,"Equipe Secrete","2023-02-15 22:00:00",500000.5,3,"pseudo_secret"\n'
        '1,11,NomPrive,"2023-02-15 21:00:00",400000.25,5,autre_pseudo\n', encoding="utf-8")
    return chemin


class TestLecture:
    """Lecture du fichier et adaptation au format des annonces."""

    def test_lit_l_archive_et_le_csv(self, jeu_kaggle, tmp_path):
        depuis_zip = evaluation_kaggle.lire_kaggle(jeu_kaggle)
        csv_seul = tmp_path / "train.csv"
        depuis_zip.to_csv(csv_seul, index=False)
        assert len(depuis_zip) == 263 and len(evaluation_kaggle.lire_kaggle(csv_seul)) == 263

    def test_fichiers_invalides(self, tmp_path):
        with pytest.raises(evaluation_kaggle.FichierKaggleInvalide, match="introuvable"):
            evaluation_kaggle.lire_kaggle(tmp_path / "absent.zip")
        archive = tmp_path / "autre.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("test.csv", "Id\n1\n")
        with pytest.raises(evaluation_kaggle.FichierKaggleInvalide, match="ne contient pas train.csv"):
            evaluation_kaggle.lire_kaggle(archive)
        mauvais = tmp_path / "mauvais.csv"
        mauvais.write_text("Rank,Score\n1,2\n", encoding="utf-8")
        with pytest.raises(evaluation_kaggle.FichierKaggleInvalide, match="Colonnes manquantes"):
            evaluation_kaggle.lire_kaggle(mauvais)

    def test_correspondance_des_colonnes(self, jeu_kaggle):
        brutes = evaluation_kaggle.lire_kaggle(jeu_kaggle)
        ligne = brutes.iloc[[0]].assign(city=[None], age=["Plus de 100 "], pieces=[None], pool=[1], garage=[1],
                                        elevator=[0], air_conditioning=[1], central_heating=[0], furnished=[1])
        annonce = evaluation_kaggle.vers_annonces(ligne)[0]
        assert annonce["ville"] == annonce["gouvernorat"] == ligne["governorate"].iloc[0]  # ville vide → gouvernorat
        assert annonce["transaction"] == "vente" and annonce["type_bien"] == "appartement"
        assert annonce["caracteristiques"] == ["climatisation", "parking", "piscine"]
        assert annonce["meuble"] is True and annonce["nb_pieces"] is None and annonce["age"] == 110.0
        assert evaluation_kaggle._age("1-5 ") == 3.0 and evaluation_kaggle._age("10,20") == 15.0

    def test_rmse(self):
        import numpy as np

        # Erreurs de 10 et 30 TND : RMSE = racine((100 + 900) / 2) = 22,36 ; MAE = 20.
        mesures = evaluation_kaggle.mesures_completes(np.array([100.0, 200.0]), np.array([110.0, 170.0]))
        assert mesures["rmse"] == 22.36 and mesures["mae"] == 20.0

    def test_classement_sans_aucun_nom(self, classement):
        scores = evaluation_kaggle.lire_classement(classement)
        assert scores == [{"rang": 1, "score": 400000.25}, {"rang": 2, "score": 500000.5}]


class TestEvaluation:
    """Référence, améliorations, comparaison avant / après."""

    @pytest.fixture
    def resultats(self, jeu_kaggle, classement, tmp_path):
        return evaluation_kaggle.evaluer(jeu_kaggle, tmp_path / "modeles", nb_arbres=10, nb_plis=3,
                                         chemin_classement=classement)

    def test_controle_qualite_du_systeme_existant(self, resultats):
        qualite = resultats["qualite_donnees"]
        assert qualite["nb_annonces_lues"] == 263
        assert qualite["valeurs_manquantes"]["nb_pieces"] == 1 and qualite["nb_incompletes_exclues"] == 1
        assert qualite["aberrantes"]["nb"] == 1 and qualite["doublons"]["nb"] >= 1
        assert resultats["separation"]["identifiants_communs"] == 0 and resultats["separation"]["contenus_communs"] == 0

    def test_avant_est_le_systeme_existant_sans_modification(self, jeu_kaggle, resultats):
        # La ligne « AVANT » doit être identique à un appel direct du système existant sur les mêmes annonces.
        annonces, _ = estimation_prix.preparer_donnees(
            evaluation_kaggle.vers_annonces(evaluation_kaggle.lire_kaggle(jeu_kaggle)))
        direct = estimation_prix.entrainer_transaction(annonces, nb_arbres=10, nb_plis=3)
        avant = next(l for l in resultats["modeles"].values() if l["role"] == "avant")
        assert avant["test"]["mape"] == direct.scores_test[direct.nom_modele]["mape"]
        assert avant["test"]["r2"] == direct.scores_test[direct.nom_modele]["r2"]
        assert avant["cv"] == direct.mape_validation_croisee[direct.nom_modele]

    def test_le_retenu_est_choisi_par_validation_croisee(self, resultats):
        lignes = resultats["modeles"]
        avec_cv = {n: l["cv"] for n, l in lignes.items() if l["cv"] is not None}
        assert resultats["retenu_apres"] == min(avec_cv, key=avec_cv.get)
        assert [n for n, l in lignes.items() if l.get("retenu")] == [resultats["retenu_apres"]]
        assert lignes[next(iter(lignes))]["cv"] is None  # la baseline n'est pas candidate
        assert len([l for l in lignes.values() if l["role"] == "amelioration"]) == 4
        for ligne in lignes.values():
            assert set(ligne["test"]) == {"mae", "mape", "r2", "rmse"} and ligne["test"]["rmse"] >= ligne["test"]["mae"]

    def test_choix_sur_la_validation_croisee_meme_si_le_test_dit_autre_chose(self):
        lignes = {
            "baseline": {"cv": None, "test": {"mape": 1.0}},          # meilleure sur le test mais pas candidate
            "existant": {"cv": 20.0, "test": {"mape": 10.0}},          # meilleur sur le test
            "piste": {"cv": 15.0, "test": {"mape": 30.0}},             # meilleure en validation croisée
        }
        assert evaluation_kaggle.choisir_apres(lignes) == "piste"

    def test_meme_jeu_de_test_avant_et_apres(self, resultats):
        par_gouvernorat = resultats["mape_par_gouvernorat"]
        assert {g: v["n"] for g, v in par_gouvernorat["avant"].items()} == \
               {g: v["n"] for g, v in par_gouvernorat["apres"].items()}
        assert sum(v["n"] for v in par_gouvernorat["avant"].values()) == resultats["separation"]["nb_test"]

    def test_rapports_ecrits_sans_toucher_aux_modeles_de_l_application(self, resultats, tmp_path):
        dossier = tmp_path / "modeles"
        assert not (dossier / estimation_prix.FICHIER_METADONNEES).exists()  # l'appli n'est pas modifiée
        assert json.loads((dossier / "kaggle" / "evaluation_kaggle.json").read_text(encoding="utf-8"))["retenu_apres"]
        rapport = (dossier / "kaggle" / "EVALUATION_KAGGLE.md").read_text(encoding="utf-8")
        for attendu in ("## Avant / après (jeu de test)", "AVANT : système existant", "**(retenu)**",
                        "## MAPE par gouvernorat", "meilleur 400 000, médiane 450 000, dernier 500 000",
                        "ce ne sont pas les mêmes annonces"):
            assert attendu in rapport, attendu

    def test_aucun_nom_du_classement_n_est_recopie(self, resultats, tmp_path):
        textes = [p.read_text(encoding="utf-8") for p in (tmp_path / "modeles" / "kaggle").iterdir()]
        for nom in ("Equipe Secrete", "pseudo_secret", "NomPrive", "autre_pseudo"):
            assert all(nom not in texte for texte in textes)


class TestCommande:
    """flask --app run evaluer-kaggle."""

    def test_commande_complete(self, app, jeu_kaggle, classement):
        resultat = app.test_cli_runner().invoke(args=[
            "evaluer-kaggle", "--fichier", str(jeu_kaggle), "--classement", str(classement), "--arbres", "10",
            "--plis", "3"])
        assert resultat.exit_code == 0, resultat.output
        for attendu in ("Contrôle qualité", "Séparation", "AVANT : système existant", "<- retenu",
                        "MAPE par gouvernorat", "Repère indicatif, classement privé Kaggle (2 équipes,",
                        "l'estimation de l'application n'est pas modifiée"):
            assert attendu in resultat.output, attendu
        resultat.output.encode("cp1252")  # affichable dans la console Windows
        assert not (Path(app.config["MODELES_FOLDER"]) / estimation_prix.FICHIER_METADONNEES).exists()

    def test_fichier_absent(self, app, tmp_path):
        resultat = app.test_cli_runner().invoke(args=["evaluer-kaggle", "--fichier", str(tmp_path / "absent.zip")])
        assert resultat.exit_code == 1 and "Fichier introuvable" in resultat.output
