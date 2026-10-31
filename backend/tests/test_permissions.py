"""Tests des permissions sur les annonces (USER-002) : visiteur, client, propriétaire A et propriétaire B."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tests.outils import ClientNavigateur

NON_AUTHENTIFIE = {"error": "non_authentifie", "message": "Veuillez vous connecter."}
PAS_PROPRIETAIRE = {"error": "forbidden", "message": "Vous ne pouvez modifier que vos propres annonces."}
RESERVE_PROPRIETAIRES = {"error": "forbidden", "message": "Espace réservé aux propriétaires."}


def image_jpeg() -> bytes:
    """Petite image JPEG valide en mémoire."""
    tampon = io.BytesIO()
    Image.new("RGB", (8, 8), color=(90, 40, 160)).save(tampon, "JPEG")
    return tampon.getvalue()


@pytest.fixture
def visiteur(app) -> ClientNavigateur:
    """Client non connecté."""
    return ClientNavigateur(app, app.response_class, use_cookies=True)


@pytest.fixture
def annonces_a(client_proprietaire, annonce_valide, villa_valide):
    """Deux annonces du propriétaire A : une publiée (avec photo) et un brouillon."""
    publiee = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    client_proprietaire.patch(f"/api/annonces/{publiee['id']}/statut", json={"statut": "publiee"})
    photo = client_proprietaire.post(
        f"/api/annonces/{publiee['id']}/photos",
        data={"photos": [(io.BytesIO(image_jpeg()), "a.jpg")]},
        content_type="multipart/form-data",
    ).get_json()["photos"][0]
    brouillon = client_proprietaire.post("/api/annonces", json=villa_valide).get_json()
    return {"publiee": publiee, "brouillon": brouillon, "photo": photo}


class TestLecture:
    """Catalogue public, « mes annonces » et fiche d'une annonce."""

    def test_le_catalogue_public_ne_renvoie_que_les_annonces_publiees(self, visiteur, client_proprietaire, annonces_a):
        # Act
        public = visiteur.get("/api/annonces").get_json()
        proprietaire_sans_filtre = client_proprietaire.get("/api/annonces").get_json()
        statut_demande = visiteur.get("/api/annonces?statut=brouillon").get_json()
        # Assert : même connecté, le catalogue public ne montre que les annonces publiées
        assert [a["id"] for a in public["items"]] == [annonces_a["publiee"]["id"]]
        assert public["total"] == 1
        assert proprietaire_sans_filtre["total"] == 1
        assert statut_demande["total"] == 0

    def test_mes_annonces_renvoie_toutes_les_annonces_du_proprietaire_connecte(
        self, client_proprietaire, client_autre_proprietaire, annonces_a
    ):
        # Act
        a = client_proprietaire.get("/api/annonces?mes_annonces=true").get_json()
        b = client_autre_proprietaire.get("/api/annonces?mes_annonces=true").get_json()
        # Assert
        assert sorted(x["id"] for x in a["items"]) == sorted([annonces_a["publiee"]["id"], annonces_a["brouillon"]["id"]])
        assert b == {"items": [], "page": 1, "per_page": 10, "total": 0}

    def test_mes_annonces_exige_un_proprietaire_connecte(self, visiteur, client_client):
        # Act / Assert
        assert visiteur.get("/api/annonces?mes_annonces=true").get_json() == NON_AUTHENTIFIE
        reponse = client_client.get("/api/annonces?mes_annonces=true")
        assert reponse.status_code == 403
        assert reponse.get_json() == RESERVE_PROPRIETAIRES

    def test_un_brouillon_n_est_visible_que_par_son_proprietaire(
        self, visiteur, client_proprietaire, client_autre_proprietaire, annonces_a
    ):
        # Arrange
        url = f"/api/annonces/{annonces_a['brouillon']['id']}"
        # Act / Assert : 404 (et non 403) pour ne pas révéler que l'annonce existe
        assert visiteur.get(url).status_code == 404
        assert client_autre_proprietaire.get(url).status_code == 404
        assert client_proprietaire.get(url).status_code == 200

    def test_la_fiche_publique_montre_le_prenom_et_la_photo_du_proprietaire(self, visiteur, client_proprietaire, annonces_a):
        # Arrange : le propriétaire ajoute une photo de profil
        url_photo = client_proprietaire.post(
            "/api/auth/moi/photo", data={"photo": (io.BytesIO(image_jpeg()), "moi.jpg")},
            content_type="multipart/form-data",
        ).get_json()["photo_profil"]
        # Act
        reponse = visiteur.get(f"/api/annonces/{annonces_a['publiee']['id']}")
        # Assert : uniquement le prénom et la photo (ni nom, ni email, ni téléphone)
        assert reponse.status_code == 200
        assert reponse.get_json()["proprietaire"] == {"prenom": "Loujain", "photo_profil": url_photo}
        texte = reponse.get_data(as_text=True)
        assert "loujain@example.com" not in texte and "Rouached" not in texte and "123 456" not in texte

    def test_un_cookie_invalide_n_empeche_pas_de_consulter_le_catalogue(self, visiteur, annonces_a):
        # Arrange : jeton corrompu (ex. session expirée côté navigateur)
        visiteur.set_cookie("access_token_cookie", "jeton.corrompu.invalide", path="/api/")
        # Act / Assert
        assert visiteur.get("/api/annonces").status_code == 200
        assert visiteur.get(f"/api/annonces/{annonces_a['publiee']['id']}").status_code == 200
        # Brouillon : le jeton est lu (utilisateur_optionnel) ; corrompu → traité comme un visiteur (404, ni 401 ni 500).
        brouillon = visiteur.get(f"/api/annonces/{annonces_a['brouillon']['id']}")
        assert brouillon.status_code == 404
        assert brouillon.get_json()["error"] == "not_found"


class TestCreation:
    """POST /api/annonces."""

    def test_le_proprietaire_connecte_devient_le_proprietaire_de_l_annonce(self, client_proprietaire, annonce_valide):
        # Arrange
        moi = client_proprietaire.get("/api/auth/moi").get_json()
        # Act
        reponse = client_proprietaire.post("/api/annonces", json=annonce_valide)
        # Assert
        assert reponse.status_code == 201
        assert reponse.get_json()["owner_id"] == moi["id"]

    def test_owner_id_ne_peut_pas_etre_choisi(self, client_proprietaire, annonce_valide):
        # Act
        reponse = client_proprietaire.post("/api/annonces", json={**annonce_valide, "owner_id": 999})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"owner_id": ["Champ inconnu."]}

    def test_reservee_aux_proprietaires(self, visiteur, client_client, annonce_valide):
        # Act
        anonyme = visiteur.post("/api/annonces", json=annonce_valide)
        client = client_client.post("/api/annonces", json=annonce_valide)
        # Assert
        assert anonyme.status_code == 401 and anonyme.get_json() == NON_AUTHENTIFIE
        assert client.status_code == 403 and client.get_json() == RESERVE_PROPRIETAIRES


ACTIONS = {
    "modifier": lambda c, a, p: c.put(f"/api/annonces/{a}", json={"prix": 1}),
    "supprimer": lambda c, a, p: c.delete(f"/api/annonces/{a}"),
    "changer_statut": lambda c, a, p: c.patch(f"/api/annonces/{a}/statut", json={"statut": "vendue"}),
    "ajouter_photos": lambda c, a, p: c.post(
        f"/api/annonces/{a}/photos", data={"photos": [(io.BytesIO(image_jpeg()), "b.jpg")]},
        content_type="multipart/form-data",
    ),
    "supprimer_photo": lambda c, a, p: c.delete(f"/api/annonces/{a}/photos/{p}"),
    "reordonner_photos": lambda c, a, p: c.patch(f"/api/annonces/{a}/photos/ordre", json={"ordre": [p]}),
}


class TestGestion:
    """Modification, suppression, statut et photos : propriétaire de l'annonce uniquement."""

    @pytest.mark.parametrize("action", ACTIONS)
    def test_un_autre_proprietaire_recoit_403_et_rien_ne_change(
        self, client_proprietaire, client_autre_proprietaire, annonces_a, action
    ):
        # Arrange
        annonce = annonces_a["publiee"]
        avant = client_proprietaire.get(f"/api/annonces/{annonce['id']}").get_json()
        # Act
        reponse = ACTIONS[action](client_autre_proprietaire, annonce["id"], annonces_a["photo"]["id"])
        # Assert
        assert reponse.status_code == 403
        assert reponse.get_json() == PAS_PROPRIETAIRE
        assert client_proprietaire.get(f"/api/annonces/{annonce['id']}").get_json() == avant

    @pytest.mark.parametrize("action", ACTIONS)
    def test_un_client_recoit_403(self, client_client, annonces_a, action):
        # Act
        reponse = ACTIONS[action](client_client, annonces_a["publiee"]["id"], annonces_a["photo"]["id"])
        # Assert
        assert reponse.status_code == 403
        assert reponse.get_json() == PAS_PROPRIETAIRE

    @pytest.mark.parametrize("action", ACTIONS)
    def test_un_visiteur_recoit_401(self, visiteur, annonces_a, action):
        # Act
        reponse = ACTIONS[action](visiteur, annonces_a["publiee"]["id"], annonces_a["photo"]["id"])
        # Assert
        assert reponse.status_code == 401
        assert reponse.get_json() == NON_AUTHENTIFIE

    @pytest.mark.parametrize("action", ACTIONS)
    def test_le_proprietaire_peut_agir_sur_son_annonce(self, client_proprietaire, annonces_a, action):
        # Act
        reponse = ACTIONS[action](client_proprietaire, annonces_a["publiee"]["id"], annonces_a["photo"]["id"])
        # Assert
        assert reponse.status_code in (200, 201, 204), reponse.get_json()

    def test_annonce_inexistante_renvoie_404(self, client_proprietaire):
        # Act
        reponse = client_proprietaire.put("/api/annonces/999", json={"prix": 1})
        # Assert
        assert reponse.status_code == 404

    def test_sans_jeton_csrf_refuse_meme_pour_le_proprietaire(self, app, client_proprietaire, annonces_a):
        # Arrange : client sans ajout automatique de l'en-tête, avec les mêmes cookies de session
        from flask.testing import FlaskClient

        brut = FlaskClient(app, app.response_class, use_cookies=True)
        for nom, chemin in (("access_token_cookie", "/api/"), ("csrf_access_token", "/")):
            cookie = client_proprietaire.get_cookie(nom, path=chemin)
            brut.set_cookie(nom, cookie.value, path=chemin)
        # Act
        reponse = brut.put(f"/api/annonces/{annonces_a['publiee']['id']}", json={"prix": 1})
        # Assert
        assert reponse.status_code == 403
        assert reponse.get_json()["error"] == "csrf_invalide"


class TestEspace:
    """Historique et statistiques : réservés aux propriétaires, limités à leurs annonces."""

    def test_un_proprietaire_ne_voit_que_son_historique_et_ses_statistiques(
        self, client_proprietaire, client_autre_proprietaire, annonces_a
    ):
        # Act
        historique_a = client_proprietaire.get("/api/historique").get_json()
        historique_b = client_autre_proprietaire.get("/api/historique").get_json()
        stats_a = client_proprietaire.get("/api/statistiques").get_json()
        stats_b = client_autre_proprietaire.get("/api/statistiques").get_json()
        frise_b = client_autre_proprietaire.get(f"/api/annonces/{annonces_a['publiee']['id']}/historique")
        # Assert
        assert historique_a["total"] == 4  # 2 créations, 1 changement de statut, 1 ajout de photos
        assert {e["annonce_id"] for e in historique_a["items"]} == {annonces_a["publiee"]["id"], annonces_a["brouillon"]["id"]}
        assert historique_b["total"] == 0
        assert (stats_a["total"], stats_b["total"]) == (2, 0)
        assert stats_b["dernieres_actions"] == []
        assert frise_b.status_code == 404

    def test_l_historique_d_une_annonce_supprimee_reste_visible_par_son_proprietaire(self, client_proprietaire, annonces_a):
        # Arrange
        annonce_id = annonces_a["brouillon"]["id"]
        client_proprietaire.delete(f"/api/annonces/{annonce_id}")
        # Act
        reponse = client_proprietaire.get(f"/api/annonces/{annonce_id}/historique")
        # Assert
        assert reponse.status_code == 200
        assert [e["action"] for e in reponse.get_json()["items"]] == ["suppression", "creation"]

    @pytest.mark.parametrize("url", ["/api/historique", "/api/statistiques", "/api/annonces/1/historique"])
    def test_reserve_aux_proprietaires(self, visiteur, client_client, url):
        # Act / Assert
        assert visiteur.get(url).status_code == 401
        reponse = client_client.get(url)
        assert reponse.status_code == 403
        assert reponse.get_json() == RESERVE_PROPRIETAIRES
