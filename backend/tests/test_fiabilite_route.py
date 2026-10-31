"""Accès propriétaire à l'état minimal du moteur de fiabilité."""

from pathlib import Path


def test_etat_fiabilite_est_reserve_au_proprietaire(client):
    response = client.get("/api/ia/fiabilite/etat")
    assert response.status_code == 401


def test_etat_fiabilite_n_expose_pas_les_chemins_du_serveur(client_proprietaire, app):
    response = client_proprietaire.get("/api/ia/fiabilite/etat")
    assert response.status_code == 200
    donnees = response.get_json()
    assert donnees["etat"] == "indisponible"
    assert donnees["modele_texte"] == "tfidf"
    assert str(Path(app.config["MODELES_FOLDER"])) not in response.get_data(as_text=True)
