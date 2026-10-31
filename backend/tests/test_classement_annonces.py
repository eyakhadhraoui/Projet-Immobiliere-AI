from pathlib import Path

import numpy as np
import pytest

from app.ia.classement_annonces import caracteristiques, classer, entrainer, generer_jeu_simule


def test_compatibilite_encode_les_criteres_de_recherche():
    vecteur = caracteristiques(
        {"ville": "Tunis", "type_bien": "appartement", "transaction": "location",
         "prix": 900, "surface": 75, "meuble": True},
        {"ville": "Tunis", "type_bien": "appartement", "transaction": "location",
         "prix_min": 500, "prix_max": 1200, "surface_min": 60, "meuble": True},
    )
    assert vecteur == [1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.75, 1.25]


def test_jeu_simule_est_regroupe_par_recherche_et_reproductible():
    x1, y1, groupes1 = generer_jeu_simule(nb_recherches=5, annonces_par_recherche=4, graine=9)
    x2, y2, groupes2 = generer_jeu_simule(nb_recherches=5, annonces_par_recherche=4, graine=9)
    assert x1.shape == (20, 10)
    assert np.array_equal(x1, x2)
    assert np.array_equal(y1, y2)
    assert groupes1.tolist() == groupes2.tolist() == [4] * 5
    assert set(y1) <= {0, 1, 2, 3}


def test_classement_revient_a_l_ordre_fourni_si_le_modele_manque(tmp_path: Path):
    annonces = [{"id": 2}, {"id": 1}]
    resultat, actif = classer(annonces, {"ville": "Tunis"}, tmp_path)
    assert actif is False
    assert resultat == annonces


def test_modele_lambdarank_fournit_des_contributions_shap(tmp_path: Path):
    pytest.importorskip("lightgbm")
    entrainer(tmp_path, graine=14)
    annonces = [
        {"id": 1, "ville": "Tunis", "type_bien": "appartement", "transaction": "location",
         "prix": 800, "surface": 80, "meuble": True},
        {"id": 2, "ville": "Sousse", "type_bien": "villa", "transaction": "vente",
         "prix": 800000, "surface": 250, "meuble": False},
    ]

    resultat, actif = classer(
        annonces,
        {"ville": "Tunis", "type_bien": "appartement", "transaction": "location",
         "prix_max": 1000, "surface_min": 60, "meuble": True},
        tmp_path,
    )

    assert actif is True
    assert resultat[0]["id"] == 1
    assert resultat[0]["classement_ia"]["explications"]
    assert all("influence" in ligne for ligne in resultat[0]["classement_ia"]["explications"])

