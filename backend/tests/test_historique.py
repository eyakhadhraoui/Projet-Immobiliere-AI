"""Tests de l'historique des annonces : enregistrement par les services et routes de consultation."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image
from sqlalchemy import select

from app import db
from app.models import AnnonceHistorique


# USER-002 : les annonces se gèrent connecté en propriétaire ; dans ce fichier, « client » est donc un
# propriétaire connecté (cookies de session + en-tête CSRF automatique, voir conftest.ClientNavigateur).
@pytest.fixture
def client(client_proprietaire):
    """Client de test connecté en tant que propriétaire."""
    return client_proprietaire


def image_jpeg() -> bytes:
    """Génère une petite image JPEG valide en mémoire.

    Returns:
        bytes: Contenu du fichier image.
    """
    tampon = io.BytesIO()
    Image.new("RGB", (8, 8), color=(30, 120, 200)).save(tampon, "JPEG")
    return tampon.getvalue()


@pytest.fixture
def annonce(creer_annonce, annonce_valide):
    """Annonce existante (son historique contient déjà l'entrée « creation »)."""
    return creer_annonce(annonce_valide)


@pytest.fixture
def historique(client):
    """Fabrique qui renvoie les entrées d'historique d'une annonce (plus récente en premier)."""

    def lire(annonce_id):
        reponse = client.get(f"/api/annonces/{annonce_id}/historique")
        assert reponse.status_code == 200, reponse.get_json()
        return reponse.get_json()["items"]

    return lire


@pytest.fixture
def ajouter_photos(client):
    """Fabrique qui ajoute ``nombre`` photos JPEG à une annonce et renvoie les photos créées."""

    def ajouter(annonce_id, nombre=1):
        donnees = {"photos": [(io.BytesIO(image_jpeg()), f"photo{i}.jpg") for i in range(nombre)]}
        reponse = client.post(f"/api/annonces/{annonce_id}/photos", data=donnees, content_type="multipart/form-data")
        assert reponse.status_code == 201, reponse.get_json()
        return reponse.get_json()["photos"]

    return ajouter


def nombre_entrees(app) -> int:
    """Nombre total d'entrées dans la table d'historique."""
    with app.app_context():
        return len(db.session.scalars(select(AnnonceHistorique)).all())


class TestEnregistrement:
    """Chaque action du service enregistre une entrée dans la même transaction."""

    def test_creation_enregistre_une_entree(self, annonce, historique):
        # Act
        entrees = historique(annonce["id"])
        # Assert
        assert len(entrees) == 1
        entree = entrees[0]
        assert entree["action"] == "creation"
        assert entree["annonce_id"] == annonce["id"]
        assert entree["titre_annonce"] == "S+2 meublé à La Marsa"
        assert entree["owner_id"] == 1
        assert entree["details"] == {
            "statut": "brouillon",
            "type_bien": "appartement",
            "transaction": "location",
            "prix": 1200,
            "ville": "La Marsa",
        }
        assert entree["created_at"].endswith("+00:00")

    def test_modification_enregistre_l_ancienne_et_la_nouvelle_valeur_des_seuls_champs_modifies(
        self, client, annonce, historique
    ):
        # Act : la ville est renvoyée inchangée, elle ne doit pas apparaître
        reponse = client.put(
            f"/api/annonces/{annonce['id']}",
            json={"prix": 950, "meuble": False, "ville": "La Marsa", "caracteristiques": ["parking"]},
        )
        # Assert
        assert reponse.status_code == 200
        entree = historique(annonce["id"])[0]
        assert entree["action"] == "modification"
        assert entree["details"] == {
            "prix": {"avant": 1200, "apres": 950},
            "meuble": {"avant": True, "apres": False},
            "caracteristiques": {"avant": ["parking", "climatisation"], "apres": ["parking"]},
        }

    def test_modification_du_titre_garde_le_nouveau_titre(self, client, annonce, historique):
        # Act
        client.put(f"/api/annonces/{annonce['id']}", json={"titre": "S+2 rénové à La Marsa"})
        # Assert
        entree = historique(annonce["id"])[0]
        assert entree["titre_annonce"] == "S+2 rénové à La Marsa"
        assert entree["details"] == {"titre": {"avant": "S+2 meublé à La Marsa", "apres": "S+2 rénové à La Marsa"}}

    def test_modification_sans_changement_n_enregistre_rien(self, client, annonce, historique):
        # Act
        client.put(f"/api/annonces/{annonce['id']}", json={"prix": 1200, "ville": "La Marsa"})
        # Assert
        assert [e["action"] for e in historique(annonce["id"])] == ["creation"]

    def test_modification_invalide_n_enregistre_rien(self, app, client, annonce):
        # Act
        reponse = client.put(f"/api/annonces/{annonce['id']}", json={"prix": -5})
        # Assert
        assert reponse.status_code == 400
        assert nombre_entrees(app) == 1

    def test_changement_de_statut(self, client, annonce, historique):
        # Act
        client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
        # Assert
        entree = historique(annonce["id"])[0]
        assert entree["action"] == "changement_statut"
        assert entree["details"] == {"avant": "brouillon", "apres": "publiee"}

    def test_statut_identique_n_enregistre_rien(self, client, annonce, historique):
        # Act
        client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "brouillon"})
        # Assert
        assert len(historique(annonce["id"])) == 1

    def test_ajout_de_photos(self, annonce, ajouter_photos, historique):
        # Act
        photos = ajouter_photos(annonce["id"], nombre=2)
        # Assert
        entree = historique(annonce["id"])[0]
        assert entree["action"] == "ajout_photos"
        assert entree["details"] == {"nombre": 2, "photo_ids": [photo["id"] for photo in photos]}

    def test_suppression_d_une_photo(self, client, annonce, ajouter_photos, historique):
        # Arrange
        photos = ajouter_photos(annonce["id"], nombre=3)
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}/photos/{photos[1]['id']}")
        # Assert
        assert reponse.status_code == 204
        entree = historique(annonce["id"])[0]
        assert entree["action"] == "suppression_photo"
        assert entree["details"] == {"photo_id": photos[1]["id"], "position": 2}

    def test_reordonnancement_des_photos(self, client, annonce, ajouter_photos, historique):
        # Arrange
        ids = [photo["id"] for photo in ajouter_photos(annonce["id"], nombre=3)]
        nouvel_ordre = [ids[2], ids[0], ids[1]]
        # Act
        client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json={"ordre": nouvel_ordre})
        # Assert
        entree = historique(annonce["id"])[0]
        assert entree["action"] == "reordonnancement_photos"
        assert entree["details"] == {"avant": ids, "apres": nouvel_ordre}

    def test_ordre_identique_n_enregistre_rien(self, client, annonce, ajouter_photos, historique):
        # Arrange
        ids = [photo["id"] for photo in ajouter_photos(annonce["id"], nombre=2)]
        # Act
        client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json={"ordre": ids})
        # Assert
        assert historique(annonce["id"])[0]["action"] == "ajout_photos"

    def test_suppression_conserve_l_historique_et_le_titre(self, client, annonce, ajouter_photos, historique):
        # Arrange
        ajouter_photos(annonce["id"], nombre=2)
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 204
        assert client.get(f"/api/annonces/{annonce['id']}").status_code == 404
        entrees = historique(annonce["id"])
        assert [e["action"] for e in entrees] == ["suppression", "ajout_photos", "creation"]
        assert entrees[0]["titre_annonce"] == "S+2 meublé à La Marsa"
        assert entrees[0]["details"] == {"statut": "brouillon", "nb_photos": 2}

    @pytest.mark.parametrize(
        "action",
        ["creation", "modification", "changement_statut", "ajout_photos", "suppression_photo",
         "reordonnancement_photos", "suppression"],
    )
    def test_action_et_historique_valides_en_un_seul_commit(
        self, client, annonce_valide, ajouter_photos, historique, monkeypatch, action
    ):
        # Arrange : annonce avec 2 photos, préparée avant de compter les commits
        cree = client.post("/api/annonces", json=annonce_valide).get_json()
        photos = ajouter_photos(cree["id"], nombre=2)
        ids = [photo["id"] for photo in photos]
        appels = []
        commit_reel = db.session.commit

        def commit_compte():
            appels.append(1)
            return commit_reel()

        monkeypatch.setattr(db.session, "commit", commit_compte)
        requetes = {
            "creation": lambda: client.post("/api/annonces", json=annonce_valide),
            "modification": lambda: client.put(f"/api/annonces/{cree['id']}", json={"prix": 999}),
            "changement_statut": lambda: client.patch(f"/api/annonces/{cree['id']}/statut", json={"statut": "publiee"}),
            "ajout_photos": lambda: client.post(
                f"/api/annonces/{cree['id']}/photos",
                data={"photos": [(io.BytesIO(image_jpeg()), "c.jpg")]},
                content_type="multipart/form-data",
            ),
            "suppression_photo": lambda: client.delete(f"/api/annonces/{cree['id']}/photos/{ids[0]}"),
            "reordonnancement_photos": lambda: client.patch(
                f"/api/annonces/{cree['id']}/photos/ordre", json={"ordre": ids[::-1]}
            ),
            "suppression": lambda: client.delete(f"/api/annonces/{cree['id']}"),
        }
        # Act
        reponse = requetes[action]()
        # Assert
        assert reponse.status_code in (200, 201, 204), reponse.get_json()
        assert len(appels) == 1
        annonce_id = reponse.get_json()["id"] if action == "creation" else cree["id"]
        assert historique(annonce_id)[0]["action"] == action

    def test_echec_du_commit_n_enregistre_ni_l_action_ni_l_historique(self, app, client, annonce, monkeypatch):
        # Arrange
        def commit_en_panne():
            raise RuntimeError("panne base simulée")

        monkeypatch.setattr(db.session, "commit", commit_en_panne)
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
        monkeypatch.undo()
        # Assert : même transaction → rien n'a été écrit
        assert reponse.status_code == 500
        assert nombre_entrees(app) == 1
        assert client.get(f"/api/annonces/{annonce['id']}").get_json()["statut"] == "brouillon"


class TestHistoriqueAnnonce:
    """GET /api/annonces/<id>/historique."""

    def test_ordre_du_plus_recent_au_plus_ancien(self, client, annonce, historique):
        # Arrange
        client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "en_attente"})
        client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
        # Act
        entrees = historique(annonce["id"])
        # Assert
        assert [e["details"].get("apres") for e in entrees] == ["publiee", "en_attente", None]

    def test_annonce_inconnue_renvoie_404(self, client):
        # Act
        reponse = client.get("/api/annonces/999/historique")
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["error"] == "not_found"

    def test_ne_contient_que_l_annonce_demandee(self, creer_annonce, annonce, villa_valide, historique):
        # Arrange
        villa = creer_annonce(villa_valide)
        # Act
        entrees = historique(villa["id"])
        # Assert
        assert [e["annonce_id"] for e in entrees] == [villa["id"]]


class TestListeHistorique:
    """GET /api/historique : filtres et pagination."""

    @pytest.fixture
    def plusieurs_actions(self, app, client, creer_annonce, annonce_valide, villa_valide):
        """Deux annonces et quatre actions, dont deux datées du 1er et du 15 octobre 2026."""
        marsa = creer_annonce(annonce_valide)
        villa = creer_annonce(villa_valide)
        client.patch(f"/api/annonces/{marsa['id']}/statut", json={"statut": "publiee"})
        client.put(f"/api/annonces/{villa['id']}", json={"prix": 440000})
        with app.app_context():
            entrees = db.session.scalars(select(AnnonceHistorique).order_by(AnnonceHistorique.id)).all()
            entrees[0].created_at = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
            entrees[1].created_at = datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc)
            db.session.commit()
        return marsa, villa

    def test_liste_toutes_les_entrees_paginees(self, client, plusieurs_actions):
        # Act
        reponse = client.get("/api/historique?per_page=3")
        # Assert
        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert donnees["total"] == 4
        assert donnees["page"] == 1
        assert donnees["per_page"] == 3
        assert len(donnees["items"]) == 3
        assert client.get("/api/historique?per_page=3&page=2").get_json()["items"][0]["action"] == "creation"

    def test_filtre_par_annonce_et_action(self, client, plusieurs_actions):
        # Arrange
        _, villa = plusieurs_actions
        # Act
        par_annonce = client.get(f"/api/historique?annonce_id={villa['id']}").get_json()
        par_action = client.get("/api/historique?action=modification").get_json()
        # Assert
        assert {e["annonce_id"] for e in par_annonce["items"]} == {villa["id"]}
        assert par_annonce["total"] == 2
        assert [e["action"] for e in par_action["items"]] == ["modification"]
        assert par_action["items"][0]["details"] == {"prix": {"avant": 450000, "apres": 440000}}

    def test_filtre_par_periode_dates_incluses(self, client, plusieurs_actions):
        # Act
        reponse = client.get("/api/historique?date_debut=2026-10-01&date_fin=2026-10-15")
        # Assert : 15/10 à 23:30 est inclus (date_fin couvre toute la journée)
        donnees = reponse.get_json()
        assert donnees["total"] == 2
        assert [e["created_at"][:10] for e in donnees["items"]] == ["2026-10-15", "2026-10-01"]

    @pytest.mark.parametrize(
        ("requete", "champ"),
        [
            ("action=inconnue", "action"),
            ("date_debut=21-10-2026", "date_debut"),
            ("date_debut=2026-10-20&date_fin=2026-10-01", "date_fin"),
            ("annonce_id=0", "annonce_id"),
            ("page=0", "page"),
        ],
    )
    def test_filtres_invalides_renvoient_400(self, client, requete, champ):
        # Act
        reponse = client.get(f"/api/historique?{requete}")
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "validation"
        assert champ in reponse.get_json()["details"]
