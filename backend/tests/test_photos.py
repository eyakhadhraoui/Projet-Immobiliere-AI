"""Tests des photos d'annonces : upload, service des fichiers, suppression, réordonnancement."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app import db
from app.models import AnnoncePhoto


# USER-002 : les annonces se gèrent connecté en propriétaire ; dans ce fichier, « client » est donc un
# propriétaire connecté (cookies de session + en-tête CSRF automatique, voir conftest.ClientNavigateur).
@pytest.fixture
def client(client_proprietaire):
    """Client de test connecté en tant que propriétaire."""
    return client_proprietaire


def image_en_octets(format_pillow: str = "JPEG") -> bytes:
    """Génère une petite image valide en mémoire.

    Args:
        format_pillow: Format Pillow (``JPEG``, ``PNG``, ``WEBP``, ``GIF``…).

    Returns:
        bytes: Contenu du fichier image.
    """
    tampon = io.BytesIO()
    Image.new("RGB", (8, 8), color=(200, 30, 30)).save(tampon, format_pillow)
    return tampon.getvalue()


@pytest.fixture
def annonce(creer_annonce, annonce_valide):
    """Annonce existante, sans photo."""
    return creer_annonce(annonce_valide)


@pytest.fixture
def envoyer_photos(client):
    """Fabrique qui envoie des fichiers ``(contenu, nom)`` dans le champ ``photos``."""

    def envoyer(annonce_id, fichiers):
        donnees = {"photos": [(io.BytesIO(contenu), nom) for contenu, nom in fichiers]}
        return client.post(f"/api/annonces/{annonce_id}/photos", data=donnees, content_type="multipart/form-data")

    return envoyer


class TestUploadPhotos:
    """POST /api/annonces/<id>/photos."""

    def test_upload_jpg_renvoie_201_et_renomme_le_fichier_avec_uuid(self, envoyer_photos, annonce, dossier_uploads):
        # Arrange
        fichiers = [(image_en_octets("JPEG"), "salon.jpg")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 201
        photo = reponse.get_json()["photos"][0]
        assert photo["annonce_id"] == annonce["id"]
        assert photo["ordre"] == 1
        assert photo["type_piece"] is None
        nom = photo["url"].removeprefix("/uploads/")
        assert photo["url"].startswith("/uploads/") and nom.endswith(".jpg")
        assert len(nom.removesuffix(".jpg")) == 32 and "salon" not in nom
        assert (dossier_uploads / nom).is_file()

    def test_upload_png_et_webp_numerotes_dans_l_ordre_d_envoi(self, envoyer_photos, annonce):
        # Arrange
        fichiers = [(image_en_octets("PNG"), "a.png"), (image_en_octets("WEBP"), "b.webp")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 201
        photos = reponse.get_json()["photos"]
        assert [p["ordre"] for p in photos] == [1, 2]
        assert photos[0]["url"].endswith(".png") and photos[1]["url"].endswith(".webp")

    def test_l_ordre_continue_apres_la_derniere_photo_existante(self, envoyer_photos, annonce):
        # Arrange
        envoyer_photos(annonce["id"], [(image_en_octets(), "1.jpg"), (image_en_octets(), "2.jpg")])
        # Act
        reponse = envoyer_photos(annonce["id"], [(image_en_octets(), "3.jpg")])
        # Assert
        assert reponse.status_code == 201
        assert reponse.get_json()["photos"][0]["ordre"] == 3

    def test_extension_non_autorisee_refusee(self, envoyer_photos, annonce):
        # Arrange
        fichiers = [(b"%PDF-1.4 faux pdf", "facture.pdf")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json() == {
            "error": "validation",
            "details": {"photos": ["facture.pdf : format non autorisé (jpg, jpeg, png, webp)."]},
        }

    def test_executable_renomme_en_jpg_refuse(self, envoyer_photos, annonce, dossier_uploads):
        # Arrange
        faux_jpg = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 200
        # Act
        reponse = envoyer_photos(annonce["id"], [(faux_jpg, "virus.jpg")])
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["photos"] == [
            "virus.jpg : le fichier n'est pas une image valide (jpg, jpeg, png, webp)."
        ]
        assert not dossier_uploads.exists() or not any(dossier_uploads.iterdir())

    def test_image_gif_renommee_en_jpg_refusee(self, envoyer_photos, annonce):
        # Arrange
        fichiers = [(image_en_octets("GIF"), "anime.jpg")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 400
        assert "anime.jpg : le fichier n'est pas une image valide" in reponse.get_json()["details"]["photos"][0]

    def test_png_nomme_jpg_enregistre_avec_l_extension_du_format_reel(self, envoyer_photos, annonce):
        # Arrange
        fichiers = [(image_en_octets("PNG"), "photo.jpg")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 201
        assert reponse.get_json()["photos"][0]["url"].endswith(".png")

    def test_nom_avec_traversee_de_repertoire_sans_effet(self, envoyer_photos, annonce, dossier_uploads, tmp_path):
        # Arrange
        fichiers = [(image_en_octets(), "../../app/__init__.jpg")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 201
        url = reponse.get_json()["photos"][0]["url"]
        assert ".." not in url and "__init__" not in url
        assert [f.name for f in dossier_uploads.iterdir()] == [url.removeprefix("/uploads/")]
        assert list(tmp_path.rglob("__init__*")) == []

    def test_un_fichier_invalide_annule_tout_l_envoi(self, envoyer_photos, annonce, dossier_uploads, client):
        # Arrange
        fichiers = [(image_en_octets(), "ok.jpg"), (b"pas une image", "ko.png")]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"]["photos"] == [
            "ko.png : le fichier n'est pas une image valide (jpg, jpeg, png, webp)."
        ]
        assert not dossier_uploads.exists() or not any(dossier_uploads.iterdir())
        assert client.get(f"/api/annonces/{annonce['id']}").get_json()["photos"] == []

    def test_aucun_fichier_refuse(self, client, annonce):
        # Arrange
        url = f"/api/annonces/{annonce['id']}/photos"
        # Act
        reponse = client.post(url, data={}, content_type="multipart/form-data")
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"photos": ["Au moins une photo est requise."]}

    def test_plus_de_10_photos_en_un_envoi_refuse(self, envoyer_photos, annonce):
        # Arrange
        fichiers = [(image_en_octets(), f"{i}.jpg") for i in range(11)]
        # Act
        reponse = envoyer_photos(annonce["id"], fichiers)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"photos": ["Maximum 10 photos par annonce (0 déjà présentes)."]}

    def test_total_de_10_photos_par_annonce_respecte(self, envoyer_photos, annonce):
        # Arrange
        envoyer_photos(annonce["id"], [(image_en_octets(), f"{i}.jpg") for i in range(8)])
        # Act
        reponse = envoyer_photos(annonce["id"], [(image_en_octets(), f"n{i}.jpg") for i in range(3)])
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json() == {
            "error": "validation",
            "details": {"photos": ["Maximum 10 photos par annonce (8 déjà présentes)."]},
        }

    def test_upload_sur_annonce_introuvable_renvoie_404(self, envoyer_photos):
        # Arrange
        fichiers = [(image_en_octets(), "salon.jpg")]
        # Act
        reponse = envoyer_photos(99, fichiers)
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["message"] == "Annonce 99 introuvable"

    def test_requete_trop_volumineuse_renvoie_413_en_francais(self, envoyer_photos, annonce, app):
        # Arrange
        trop_gros = b"\xff" * (app.config["MAX_CONTENT_LENGTH"] + 1)
        # Act
        reponse = envoyer_photos(annonce["id"], [(trop_gros, "enorme.jpg")])
        # Assert
        assert reponse.status_code == 413
        assert reponse.get_json() == {
            "error": "request_entity_too_large",
            "message": "La requête dépasse la taille maximale autorisée (5 Mo).",
        }

    def test_echec_base_de_donnees_supprime_les_fichiers_deja_ecrits(
        self, envoyer_photos, annonce, dossier_uploads, monkeypatch
    ):
        # Arrange
        def commit_en_panne():
            raise RuntimeError("panne base simulée")

        monkeypatch.setattr(db.session, "commit", commit_en_panne)
        # Act
        reponse = envoyer_photos(annonce["id"], [(image_en_octets(), "a.jpg"), (image_en_octets(), "b.jpg")])
        # Assert
        assert reponse.status_code == 500
        assert list(dossier_uploads.iterdir()) == []

    def test_photos_visibles_dans_le_detail_de_l_annonce(self, envoyer_photos, annonce, client):
        # Arrange
        envoyer_photos(annonce["id"], [(image_en_octets(), "a.jpg"), (image_en_octets(), "b.jpg")])
        # Act
        reponse = client.get(f"/api/annonces/{annonce['id']}")
        # Assert
        assert [p["ordre"] for p in reponse.get_json()["photos"]] == [1, 2]


class TestServirPhotos:
    """GET /uploads/<filename>."""

    def test_image_servie_avec_son_contenu(self, envoyer_photos, annonce, client):
        # Arrange
        contenu = image_en_octets("JPEG")
        url = envoyer_photos(annonce["id"], [(contenu, "a.jpg")]).get_json()["photos"][0]["url"]
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 200
        assert reponse.mimetype == "image/jpeg"
        assert reponse.data == contenu
        assert reponse.headers["X-Content-Type-Options"] == "nosniff"
        reponse.close()

    def test_fichier_inexistant_renvoie_404_en_json(self, client):
        # Arrange
        url = "/uploads/inexistant.jpg"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["error"] == "not_found"

    def test_traversee_de_repertoire_refusee(self, client):
        # Arrange
        url = "/uploads/..%5C..%5Capp%5Cconfig.py"
        # Act
        reponse = client.get(url)
        # Assert
        assert reponse.status_code == 404


class TestSuppressionPhoto:
    """DELETE /api/annonces/<id>/photos/<photo_id>."""

    def test_suppression_retire_la_photo_de_la_base_et_du_disque(
        self, envoyer_photos, annonce, client, app, dossier_uploads
    ):
        # Arrange
        photo = envoyer_photos(annonce["id"], [(image_en_octets(), "a.jpg")]).get_json()["photos"][0]
        fichier = dossier_uploads / photo["url"].removeprefix("/uploads/")
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}/photos/{photo['id']}")
        # Assert
        assert reponse.status_code == 204
        assert not fichier.exists()
        with app.app_context():
            assert db.session.get(AnnoncePhoto, photo["id"]) is None

    def test_photo_d_une_autre_annonce_renvoie_404(
        self, envoyer_photos, creer_annonce, annonce, villa_valide, client
    ):
        # Arrange
        autre = creer_annonce(villa_valide)
        photo = envoyer_photos(autre["id"], [(image_en_octets(), "a.jpg")]).get_json()["photos"][0]
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}/photos/{photo['id']}")
        # Assert
        assert reponse.status_code == 404
        assert reponse.get_json()["message"] == f"Photo {photo['id']} introuvable pour l'annonce {annonce['id']}"

    def test_photo_inexistante_renvoie_404(self, client, annonce):
        # Arrange
        url = f"/api/annonces/{annonce['id']}/photos/99"
        # Act
        reponse = client.delete(url)
        # Assert
        assert reponse.status_code == 404


class TestOrdrePhotos:
    """PATCH /api/annonces/<id>/photos/ordre."""

    @pytest.fixture
    def ids_photos(self, envoyer_photos, annonce):
        """Trois photos ajoutées à l'annonce, renvoie leurs ids dans l'ordre initial."""
        reponse = envoyer_photos(annonce["id"], [(image_en_octets(), f"{i}.jpg") for i in range(3)])
        return [p["id"] for p in reponse.get_json()["photos"]]

    def test_reordonnancement_valide(self, client, annonce, ids_photos):
        # Arrange
        nouvel_ordre = list(reversed(ids_photos))
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json={"ordre": nouvel_ordre})
        # Assert
        assert reponse.status_code == 200
        photos = reponse.get_json()["photos"]
        assert [p["id"] for p in photos] == nouvel_ordre
        assert [p["ordre"] for p in photos] == [1, 2, 3]
        detail = client.get(f"/api/annonces/{annonce['id']}").get_json()
        assert [p["id"] for p in detail["photos"]] == nouvel_ordre

    def test_liste_incomplete_refusee(self, client, annonce, ids_photos):
        # Arrange
        incomplete = ids_photos[:2]
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json={"ordre": incomplete})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {
            "ordre": [f"La liste doit contenir exactement les photos de l'annonce : {sorted(ids_photos)}."]
        }

    def test_doublons_refuses(self, client, annonce, ids_photos):
        # Arrange
        avec_doublon = [ids_photos[0], ids_photos[0], ids_photos[1]]
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json={"ordre": avec_doublon})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"ordre": ["La liste contient des identifiants en double."]}

    def test_liste_vide_refusee(self, client, annonce):
        # Arrange
        corps = {"ordre": []}
        # Act
        reponse = client.patch(f"/api/annonces/{annonce['id']}/photos/ordre", json=corps)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"ordre": ["La liste ne peut pas être vide."]}

    def test_annonce_introuvable_renvoie_404(self, client):
        # Arrange
        corps = {"ordre": [1]}
        # Act
        reponse = client.patch("/api/annonces/99/photos/ordre", json=corps)
        # Assert
        assert reponse.status_code == 404


class TestSuppressionAnnonceAvecPhotos:
    """DELETE /api/annonces/<id> : les fichiers des photos sont supprimés du disque."""

    def test_suppression_annonce_supprime_les_fichiers(self, envoyer_photos, annonce, client, dossier_uploads):
        # Arrange
        envoyer_photos(annonce["id"], [(image_en_octets(), "a.jpg"), (image_en_octets("PNG"), "b.png")])
        assert len(list(dossier_uploads.iterdir())) == 2
        # Act
        reponse = client.delete(f"/api/annonces/{annonce['id']}")
        # Assert
        assert reponse.status_code == 204
        assert list(dossier_uploads.iterdir()) == []
