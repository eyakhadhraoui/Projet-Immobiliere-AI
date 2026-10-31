"""Tests de GET /api/statistiques."""

from __future__ import annotations

import pytest


# USER-002 : les annonces se gèrent connecté en propriétaire ; dans ce fichier, « client » est donc un
# propriétaire connecté (cookies de session + en-tête CSRF automatique, voir conftest.ClientNavigateur).
@pytest.fixture
def client(client_proprietaire):
    """Client de test connecté en tant que propriétaire."""
    return client_proprietaire


class TestStatistiques:
    """Nombre d'annonces par statut et par type, prix moyen par transaction, dernières actions."""

    def test_base_vide(self, client):
        # Act
        reponse = client.get("/api/statistiques")
        # Assert
        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert donnees["total"] == 0
        assert donnees["par_statut"] == {
            "brouillon": 0, "en_attente": 0, "publiee": 0, "louee": 0, "vendue": 0,
        }
        assert donnees["par_type"] == {
            "appartement": 0, "maison": 0, "studio": 0, "villa": 0, "residence": 0,
        }
        assert donnees["prix_moyen"] == {"vente": None, "location": None}
        assert donnees["dernieres_actions"] == []
        assert donnees["maintenances_ouvertes"] == 0
        assert donnees["maintenances_urgentes"] == 0
        assert donnees["loyers_a_encaisser"] == []

    def test_comptes_et_prix_moyens(self, client, creer_annonce, annonce_valide, villa_valide):
        # Arrange : 2 locations (1200 et 800), 1 vente (450000)
        marsa = creer_annonce(annonce_valide)
        creer_annonce({**annonce_valide, "titre": "Studio à Tunis", "type_bien": "studio", "prix": 800})
        creer_annonce(villa_valide)
        client.patch(f"/api/annonces/{marsa['id']}/statut", json={"statut": "publiee"})
        # Act
        donnees = client.get("/api/statistiques").get_json()
        # Assert
        assert donnees["total"] == 3
        assert donnees["par_statut"] == {"brouillon": 2, "en_attente": 0, "publiee": 1, "louee": 0, "vendue": 0}
        assert donnees["par_type"] == {"appartement": 1, "maison": 0, "studio": 1, "villa": 1, "residence": 0}
        assert donnees["prix_moyen"] == {"vente": 450000, "location": 1000}

    def test_cinq_dernieres_actions_de_la_plus_recente_a_la_plus_ancienne(self, client, creer_annonce, annonce_valide):
        # Arrange : 1 création + 5 changements de statut = 6 actions
        annonce = creer_annonce(annonce_valide)
        for statut in ["en_attente", "publiee", "louee", "publiee", "brouillon"]:
            client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": statut})
        # Act
        actions = client.get("/api/statistiques").get_json()["dernieres_actions"]
        # Assert
        assert len(actions) == 5
        assert [a["details"]["apres"] for a in actions] == ["brouillon", "publiee", "louee", "publiee", "en_attente"]

    def test_les_annonces_supprimees_ne_sont_plus_comptees_mais_restent_dans_les_actions(
        self, client, creer_annonce, annonce_valide
    ):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        client.delete(f"/api/annonces/{annonce['id']}")
        # Act
        donnees = client.get("/api/statistiques").get_json()
        # Assert
        assert donnees["total"] == 0
        assert donnees["prix_moyen"]["location"] is None
        assert [a["action"] for a in donnees["dernieres_actions"]] == ["suppression", "creation"]
