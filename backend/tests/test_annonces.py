"""Tests de l'API REST /api/annonces (cas de CRUD-002, rendus relançables)."""

from __future__ import annotations

import pytest

from app import db
from app.models import Annonce, AnnoncePhoto


# USER-002 : les annonces se gèrent connecté en propriétaire ; dans ce fichier, « client » est donc un
# propriétaire connecté (cookies de session + en-tête CSRF automatique, voir conftest.ClientNavigateur).
@pytest.fixture
def client(client_proprietaire):
    """Client de test connecté en tant que propriétaire."""
    return client_proprietaire


class TestCreation:
    """POST /api/annonces."""

    def test_creation_valide_renvoie_201_et_statut_brouillon(self, client, annonce_valide):
        # Arrange
        donnees = annonce_valide
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 201
        corps = reponse.get_json()
        assert corps["id"] == 1
        assert corps["statut"] == "brouillon"
        assert corps["titre"] == "S+2 meublé à La Marsa"
        assert corps["caracteristiques"] == ["parking", "climatisation"]
        assert corps["photos"] == []

    def test_creation_champs_manquants_refusee(self, client):
        # Arrange
        donnees = {}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        corps = reponse.get_json()
        assert corps["error"] == "validation"
        assert set(corps["details"]) == {
            "titre", "description", "type_bien", "transaction", "prix",
            "surface", "nb_pieces", "adresse", "ville",
        }
        assert corps["details"]["titre"] == ["Champ obligatoire."]

    def test_creation_prix_nul_refuse(self, client, annonce_valide):
        # Arrange
        donnees = {**annonce_valide, "prix": 0}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["prix"] == ["Doit être supérieur à 0."]

    def test_creation_titre_trop_court_refuse(self, client, annonce_valide):
        # Arrange
        donnees = {**annonce_valide, "titre": "abc"}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["titre"] == ["Doit contenir entre 5 et 150 caractères."]

    def test_creation_type_bien_invalide_refuse(self, client, annonce_valide):
        # Arrange
        donnees = {**annonce_valide, "type_bien": "chateau"}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["type_bien"] == [
            "Doit être l'une des valeurs : appartement, maison, studio, villa, residence."
        ]

    def test_creation_nb_pieces_negatif_refuse(self, client, annonce_valide):
        # Arrange
        donnees = {**annonce_valide, "nb_pieces": -1}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["nb_pieces"] == ["Doit être supérieur ou égal à 0."]

    def test_creation_statut_impose_refuse(self, client, annonce_valide):
        # Arrange
        donnees = {**annonce_valide, "statut": "publiee"}
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["statut"] == ["Champ inconnu."]

    def test_creation_json_mal_forme_renvoie_400_en_francais(self, client):
        # Arrange
        corps_invalide = "{pas du json"
        # Act
        reponse = client.post("/api/annonces", data=corps_invalide, content_type="application/json")
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json() == {
            "error": "bad_request",
            "message": "Le corps de la requête n'est pas un JSON valide.",
        }

    def test_creation_sans_content_type_json_renvoie_415_en_francais(self, client):
        # Arrange
        corps_texte = "titre=Studio"
        # Act
        reponse = client.post("/api/annonces", data=corps_texte, content_type="text/plain")
        # Assert
        assert reponse.status_code == 415
        assert reponse.get_json()["message"] == "Le Content-Type de la requête doit être « application/json »."

    def test_reponse_json_contient_accents_lisibles(self, client, annonce_valide):
        # Arrange
        donnees = annonce_valide
        # Act
        reponse = client.post("/api/annonces", json=donnees)
        # Assert
        assert "S+2 meublé à La Marsa".encode("utf-8") in reponse.data
        assert b"\\u00e9" not in reponse.data


class TestLecture:
    """GET /api/annonces/<id>."""

    def test_detail_annonce_existante_renvoie_200(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.get(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json() == annonce

    def test_detail_annonce_introuvable_renvoie_404(self, client):
        # Arrange
        id_inexistant = 99
        # Act
        reponse = client.get(f"/api/annonces/{id_inexistant}")
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json() == {"error": "not_found", "message": "Annonce 99 introuvable"}


class TestListe:
    """GET /api/annonces."""

    def test_liste_sans_filtre_renvoie_toutes_les_annonces_recentes_d_abord(
        self, client, creer_annonce, annonce_valide, villa_valide
    ):
        # Arrange
        marsa = creer_annonce(annonce_valide)
        villa = creer_annonce(villa_valide)
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true")
        # Assert
        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert [a["id"] for a in corps["items"]] == [villa["id"], marsa["id"]]
        assert (corps["page"], corps["per_page"], corps["total"]) == (1, 10, 2)

    def test_liste_vide_renvoie_total_zero(self, client):
        # Arrange : base vide
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true")
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json() == {"items": [], "page": 1, "per_page": 10, "total": 0}

    def test_tri_pertinence_revient_au_chronologique_si_le_modele_est_absent(
        self, client, creer_annonce, annonce_valide, villa_valide
    ):
        annonce1 = creer_annonce(annonce_valide)
        annonce2 = creer_annonce(villa_valide)
        client.patch(f"/api/annonces/{annonce1['id']}/statut", json={"statut": "publiee"})
        client.patch(f"/api/annonces/{annonce2['id']}/statut", json={"statut": "publiee"})

        reponse = client.get("/api/annonces?tri=pertinence")

        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert donnees["tri_demande"] == "pertinence"
        assert donnees["tri_applique"] == "chronologique"
        assert donnees["items"][0]["id"] == annonce2["id"]
        assert "indisponible" in donnees["message_classement"]

    def test_tri_pertinence_utilise_le_modele_entraine_et_retourne_les_explications(
        self, app, client, creer_annonce, annonce_valide
    ):
        from pathlib import Path

        from app import db
        from app.ia.classement_annonces import entrainer
        from app.models import Annonce, StatutAnnonce

        with app.app_context():
            entrainer(Path(app.config["MODELES_FOLDER"]), graine=31)
        moins_chere = creer_annonce({**annonce_valide, "titre": "Appartement bien situé", "prix": 700, "surface": 100})
        plus_chere = creer_annonce({**annonce_valide, "titre": "Appartement à Tunis centre", "prix": 1400, "surface": 55})
        with app.app_context():
            for annonce_id in (moins_chere["id"], plus_chere["id"]):
                db.session.get(Annonce, annonce_id).statut = StatutAnnonce.PUBLIEE
            db.session.commit()

        reponse = client.get("/api/annonces?tri=pertinence")

        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert donnees["tri_applique"] == "pertinence"
        assert donnees["items"][0]["id"] == moins_chere["id"]
        assert donnees["items"][0]["classement_ia"]["explications"]

    def test_liste_filtres_ville_meuble_prix_max(self, client, creer_annonce, annonce_valide, villa_valide):
        # Arrange
        marsa = creer_annonce(annonce_valide)
        creer_annonce(villa_valide)
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true&ville=marsa&meuble=true&prix_max=1500")
        # Assert
        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert [a["id"] for a in corps["items"]] == [marsa["id"]]
        assert corps["total"] == 1

    def test_liste_filtres_transaction_surface_min(self, client, creer_annonce, annonce_valide, villa_valide):
        # Arrange
        creer_annonce(annonce_valide)
        villa = creer_annonce(villa_valide)
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true&transaction=vente&surface_min=200")
        # Assert
        assert reponse.status_code == 200
        assert [a["id"] for a in reponse.get_json()["items"]] == [villa["id"]]

    def test_liste_filtres_type_bien_statut_prix_min(self, client, creer_annonce, annonce_valide, villa_valide):
        # Arrange
        creer_annonce(annonce_valide)
        villa = creer_annonce(villa_valide)
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true&type_bien=villa&statut=brouillon&prix_min=100000")
        # Assert
        assert reponse.status_code == 200
        assert [a["id"] for a in reponse.get_json()["items"]] == [villa["id"]]

    def test_liste_prix_min_superieur_a_prix_max_refuse(self, client):
        # Arrange
        url = "/api/annonces?mes_annonces=true&prix_min=2000&prix_max=1000"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"prix_max": ["Doit être supérieur ou égal à prix_min."]}

    def test_liste_page_zero_et_type_bien_invalide_refuses(self, client):
        # Arrange
        url = "/api/annonces?mes_annonces=true&type_bien=chateau&page=0"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 400
        assert set(reponse.get_json()["details"]) == {"page", "type_bien"}

    def test_liste_pagination_page_2(self, client, creer_annonce, annonce_valide, villa_valide):
        # Arrange
        marsa = creer_annonce(annonce_valide)
        creer_annonce(villa_valide)
        # Act
        reponse = client.get("/api/annonces?mes_annonces=true&per_page=1&page=2")
        # Assert
        corps = reponse.get_json()
        assert reponse.status_code == 200
        assert [a["id"] for a in corps["items"]] == [marsa["id"]]
        assert (corps["page"], corps["per_page"], corps["total"]) == (2, 1, 2)

    def test_liste_per_page_plafonne_a_50(self, client):
        # Arrange
        url = "/api/annonces?mes_annonces=true&per_page=100"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json()["per_page"] == 50


class TestModification:
    """PUT /api/annonces/<id>."""

    def test_modification_partielle_conserve_les_autres_champs(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        modifications = {"prix": 1300, "titre": "S+2 meublé à La Marsa - vue mer"}
        # Act
        reponse = client.put(f"/api/annonces/{annonce['id']}", json=modifications)
        # Assert
        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps["prix"] == 1300
        assert corps["titre"] == "S+2 meublé à La Marsa - vue mer"
        assert corps["meuble"] is True
        assert corps["surface"] == annonce["surface"]

    def test_modification_valeur_invalide_refusee(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.put(f"/api/annonces/{annonce['id']}", json={"surface": -5})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"surface": ["Doit être supérieur à 0."]}

    def test_modification_owner_id_refusee(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.put(f"/api/annonces/{annonce['id']}", json={"owner_id": 9})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"owner_id": ["Champ inconnu."]}

    def test_modification_annonce_introuvable_renvoie_404(self, client):
        # Arrange
        id_inexistant = 99
        # Act
        reponse = client.put(f"/api/annonces/{id_inexistant}", json={"prix": 10})
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["message"] == "Annonce 99 introuvable"


class TestStatut:
    """PATCH /api/annonces/<id>/statut."""

    def test_changement_statut_valide(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json()["statut"] == "publiee"

    def test_changement_statut_invalide_refuse(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "archivee"})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["statut"] == [
            "Doit être l'une des valeurs : brouillon, en_attente, publiee, louee, vendue."
        ]

    def test_changement_statut_annonce_introuvable_renvoie_404(self, client):
        # Arrange
        id_inexistant = 99
        # Act
        reponse = client.patch(f"/api/annonces/{id_inexistant}/statut", json={"statut": "publiee"})
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["error"] == "not_found"


class TestSuppression:
    """DELETE /api/annonces/<id>."""

    def test_suppression_renvoie_204_sans_contenu(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 204
        assert reponse.data == b""
        assert client.get(f"/api/annonces/{annonce['id']}").status_code == 404

    def test_suppression_supprime_aussi_les_photos(self, app, client, creer_annonce, villa_valide):
        # Arrange
        annonce = creer_annonce(villa_valide)
        with app.app_context():
            db.session.add(AnnoncePhoto(annonce_id=annonce["id"], url="/uploads/villa.jpg", ordre=1))
            db.session.commit()
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 204
        with app.app_context():
            assert db.session.query(AnnoncePhoto).filter_by(annonce_id=annonce["id"]).count() == 0
            assert db.session.get(Annonce, annonce["id"]) is None

    def test_deuxieme_suppression_renvoie_404(self, client, creer_annonce, annonce_valide):
        # Arrange
        annonce = creer_annonce(annonce_valide)
        client.delete(f"/api/annonces/{annonce['id']}")
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["message"] == f"Annonce {annonce['id']} introuvable"


class TestErreursEtNonRegression:
    """Gestionnaires d'erreurs globaux et route /api/health."""

    def test_health_renvoie_200(self, client):
        # Arrange
        url = "/api/health"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json() == {"status": "ok"}

    def test_url_inconnue_renvoie_404_en_json(self, client):
        # Arrange
        url = "/api/inexistant"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["error"] == "not_found"

    def test_erreur_inattendue_renvoie_500_en_json(self, app):
        # Arrange
        def route_qui_plante():
            raise RuntimeError("panne simulée")

        app.add_url_rule("/api/test-500", "test_500", route_qui_plante)
        client = app.test_client()
        # Act
        reponse = client.get("/api/test-500")
        # Assert
        assert reponse.status_code == 500
        assert reponse.get_json() == {"error": "internal_error", "message": "Erreur interne du serveur"}
