"""Tests du pipeline non supervisé d'atypicité des annonces."""
from __future__ import annotations

import numpy as np
import pytest

from app.ia import anomalies_annonces as aa


def jeu_synthetique(n: int = 180) -> list[dict]:
    """Fixture artificielle de test; elle ne représente pas des observations réelles."""
    return [{"prix": 180000 + (i % 30) * 3000, "surface": 75 + (i % 25) * 2,
             "nb_pieces": 2 + i % 5, "transaction": "vente", "type_bien": "appartement",
             "ville": f"ville-{i % 5}"} for i in range(n)]


def test_validation_rejette_donnees_invalides():
    annonce = jeu_synthetique(1)[0] | {"prix": float("nan")}
    with pytest.raises(aa.DonneesAnnoncesInvalides):
        aa._normaliser([annonce])


def test_entraine_calibre_sur_validation_et_charge(tmp_path):
    rapport = aa.entrainer(jeu_synthetique(), tmp_path, graine=12)
    modele = aa.charger(tmp_path)
    resultat = aa.analyser(jeu_synthetique(1)[0], tmp_path)
    assert rapport["n_train"] + rapport["n_validation"] + rapport["n_test"] + rapport["n_doublons_exclus"] == 180
    assert rapport["doublons_identiques_inter_splits"] == 0
    assert rapport["test"]["metriques_supervisees"] is None
    assert modele["seuil"] == float(np.quantile(modele["scores_validation"], .95))
    assert 0 <= resultat["score_anomalie"] <= 1
    assert resultat["niveau"] in {"habituel", "à_verifier"}


def test_seuil_marque_une_observation_extreme(tmp_path):
    aa.entrainer(jeu_synthetique(), tmp_path)
    extreme = {"prix": 15000000, "surface": 1000, "nb_pieces": 30,
               "transaction": "vente", "type_bien": "villa", "ville": "ville-rare"}
    assert aa.analyser(extreme, tmp_path)["niveau"] == "à_verifier"


def test_modele_absent_est_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):
        aa.charger(tmp_path)


def test_api_analyse_annonce_est_protegee_et_limitee_au_proprietaire(
    client, client_proprietaire, client_autre_proprietaire, annonce_valide, creer_annonce, monkeypatch
):
    assert client.post("/api/ia/annonces/1/analyser-anomalie").status_code == 401
    creation = client_proprietaire.post("/api/annonces", json=annonce_valide)
    assert creation.status_code == 201, creation.get_json()
    annonce = creation.get_json()
    monkeypatch.setattr(aa, "analyser", lambda *_: {"disponible": True, "niveau": "habituel",
                                                      "score_anomalie": .2, "facteurs": []})
    assert client_autre_proprietaire.post(f"/api/ia/annonces/{annonce['id']}/analyser-anomalie").status_code == 403
    reponse = client_proprietaire.post(f"/api/ia/annonces/{annonce['id']}/analyser-anomalie")
    assert reponse.status_code == 200
    assert reponse.get_json()["score_anomalie"] == .2
