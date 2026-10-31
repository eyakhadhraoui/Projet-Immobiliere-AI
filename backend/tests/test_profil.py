"""Tests du compte de l'utilisateur connecté : lecture, modification, mot de passe, photo, suppression."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app import db
from app.models import Annonce, AnnonceHistorique, Utilisateur, UtilisateurHistorique
from tests.outils import MAUVAIS_MOT_DE_PASSE, MOT_DE_PASSE, entete_csrf, mot_de_passe_aleatoire

NOUVEAU_MOT_DE_PASSE = mot_de_passe_aleatoire()


def image_jpeg() -> bytes:
    """Petite image JPEG valide en mémoire."""
    tampon = io.BytesIO()
    Image.new("RGB", (8, 8), color=(10, 160, 90)).save(tampon, "JPEG")
    return tampon.getvalue()


def actions(app) -> list[str]:
    """Actions de l'historique des utilisateurs, de la plus ancienne à la plus récente."""
    with app.app_context():
        return [e.action.value for e in db.session.scalars(select(UtilisateurHistorique).order_by(UtilisateurHistorique.id))]


def derniere_entree(app) -> dict:
    """Dernière entrée de l'historique des utilisateurs."""
    with app.app_context():
        return db.session.scalars(select(UtilisateurHistorique).order_by(UtilisateurHistorique.id.desc())).first().to_dict()


class TestLecture:
    """GET /api/auth/moi."""

    def test_renvoie_le_compte_sans_donnees_sensibles(self, client, compte):
        # Act
        reponse = client.get("/api/auth/moi")
        # Assert
        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert set(donnees) == {
            "id", "nom", "prenom", "email", "telephone", "role", "date_naissance", "ville", "adresse",
            "photo_profil", "cin_numero", "cin_verifiee", "visage_verifie", "derniere_connexion",
            "created_at", "updated_at",
        }
        assert donnees["nom"] == "Rouached" and donnees["prenom"] == "Loujain"
        assert donnees["cin_numero"] == "******78"
        texte = reponse.get_data(as_text=True)
        assert "12345678" not in texte and "scrypt" not in texte and MOT_DE_PASSE not in texte


class TestModification:
    """PUT /api/auth/moi."""

    def test_modifie_les_champs_envoyes_et_historise(self, app, client, compte):
        # Act
        reponse = client.put(
            "/api/auth/moi",
            json={"ville": "Sousse", "telephone": "+216 98 000 111", "date_naissance": "1999-04-12", "nom": "Rouached"},
            headers=entete_csrf(client),
        )
        # Assert
        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert (donnees["ville"], donnees["date_naissance"]) == ("Sousse", "1999-04-12")
        entree = derniere_entree(app)
        assert entree["action"] == "modification"
        assert entree["details"] == {
            "ville": {"avant": "Tunis", "apres": "Sousse"},
            "telephone": {"avant": "+216 20 123 456", "apres": "+216 98 000 111"},
            "date_naissance": {"avant": None, "apres": "1999-04-12"},
        }

    def test_aucun_changement_aucun_historique(self, app, client, compte):
        # Act
        client.put("/api/auth/moi", json={"ville": "Tunis"}, headers=entete_csrf(client))
        # Assert
        assert actions(app) == ["creation"]

    def test_role_non_modifiable(self, client, compte):
        # Act
        reponse = client.put("/api/auth/moi", json={"role": "client"}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"role": ["Champ inconnu."]}
        assert client.get("/api/auth/moi").get_json()["role"] == "proprietaire"

    @pytest.mark.parametrize("champ", ["mot_de_passe", "mot_de_passe_hash", "cin_verifiee", "visage_verifie", "id"])
    def test_champs_proteges_refuses(self, client, compte, champ):
        # Act
        reponse = client.put("/api/auth/moi", json={champ: "x"}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {champ: ["Champ inconnu."]}

    def test_email_deja_utilise_par_un_autre_compte(self, app, client, compte, donnees_inscription):
        # Arrange : un second compte (depuis un autre client)
        autre = app.test_client()
        autre.post("/api/auth/inscription", json={**donnees_inscription, "email": "autre@example.com", "cin_numero": None})
        # Act
        reponse = client.put("/api/auth/moi", json={"email": "Autre@Example.com"}, headers=entete_csrf(client))
        meme_email = client.put("/api/auth/moi", json={"email": "LOUJAIN@example.com"}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 409
        assert reponse.get_json() == {"error": "conflit", "message": "Un compte existe déjà avec cet email."}
        assert meme_email.status_code == 200

    def test_email_pris_entre_la_verification_et_l_ecriture(self, app, client, compte, donnees_inscription, monkeypatch):
        # Arrange : la vérification préalable ne voit pas l'autre compte (course) ; la base refuse.
        from app.services import utilisateur_service

        app.test_client().post("/api/auth/inscription", json={**donnees_inscription, "email": "autre@example.com", "cin_numero": None})
        monkeypatch.setattr(utilisateur_service, "_valider_unicite", lambda *args, **kwargs: None)
        # Act
        reponse = client.put("/api/auth/moi", json={"email": "autre@example.com"}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 409
        assert client.get("/api/auth/moi").get_json()["email"] == "loujain@example.com"

    def test_changer_de_cin_annule_la_verification_et_masque_l_historique(self, app, client, compte):
        # Arrange : CIN vérifiée (par la future fonctionnalité d'IA)
        with app.app_context():
            db.session.get(Utilisateur, compte["id"]).cin_verifiee = True
            db.session.commit()
        # Act
        reponse = client.put("/api/auth/moi", json={"cin_numero": "87654321"}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json()["cin_numero"] == "******21"
        assert reponse.get_json()["cin_verifiee"] is False
        details = derniere_entree(app)["details"]
        assert details == {
            "cin_numero": {"avant": "******78", "apres": "******21"},
            "cin_verifiee": {"avant": True, "apres": False},
        }


class TestMotDePasse:
    """PUT /api/auth/moi/mot-de-passe."""

    URL = "/api/auth/moi/mot-de-passe"

    def test_changement_reussi_et_anciennes_sessions_fermees(self, app, client, compte):
        # Arrange : une autre session ouverte avec l'ancien mot de passe
        autre_session = app.test_client()
        autre_session.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE})
        # Act
        reponse = client.put(
            self.URL, json={"ancien_mot_de_passe": MOT_DE_PASSE, "nouveau_mot_de_passe": NOUVEAU_MOT_DE_PASSE},
            headers=entete_csrf(client),
        )
        # Assert
        assert reponse.status_code == 200
        assert client.get("/api/auth/moi").status_code == 200  # cette session a reçu de nouveaux jetons
        assert autre_session.get("/api/auth/moi").status_code == 401  # l'autre session est fermée
        connexion = app.test_client()
        assert connexion.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE}).status_code == 401
        assert connexion.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": NOUVEAU_MOT_DE_PASSE}).status_code == 200
        assert "changement_mot_de_passe" in actions(app)
        assert NOUVEAU_MOT_DE_PASSE not in str(derniere_entree(app))

    @pytest.mark.parametrize(
        ("corps", "champ", "message"),
        [
            ({"ancien_mot_de_passe": MAUVAIS_MOT_DE_PASSE, "nouveau_mot_de_passe": NOUVEAU_MOT_DE_PASSE}, "ancien_mot_de_passe", "Mot de passe incorrect."),
            ({"ancien_mot_de_passe": MOT_DE_PASSE, "nouveau_mot_de_passe": MOT_DE_PASSE}, "nouveau_mot_de_passe", "Doit être différent de l'ancien mot de passe."),
            ({"ancien_mot_de_passe": MOT_DE_PASSE, "nouveau_mot_de_passe": "court"}, "nouveau_mot_de_passe", "Doit contenir au moins 8 caractères."),
            ({"nouveau_mot_de_passe": NOUVEAU_MOT_DE_PASSE}, "ancien_mot_de_passe", "Champ obligatoire."),
        ],
    )
    def test_changements_refuses(self, client, compte, corps, champ, message):
        # Act
        reponse = client.put(self.URL, json=corps, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 400
        assert message in reponse.get_json()["details"][champ]


class TestPhoto:
    """POST et DELETE /api/auth/moi/photo."""

    URL = "/api/auth/moi/photo"

    def envoyer(self, client, contenu, nom):
        return client.post(self.URL, data={"photo": (io.BytesIO(contenu), nom)},
                           content_type="multipart/form-data", headers=entete_csrf(client))

    def test_ajout_puis_remplacement_supprime_l_ancien_fichier(self, client, compte, dossier_uploads):
        # Act
        premiere = self.envoyer(client, image_jpeg(), "moi.jpg").get_json()["photo_profil"]
        seconde = self.envoyer(client, image_jpeg(), "moi2.jpg").get_json()["photo_profil"]
        # Assert
        assert premiere.startswith("/uploads/") and premiere.endswith(".jpg") and "moi" not in premiere
        assert not (dossier_uploads / Path(premiere).name).exists()
        assert (dossier_uploads / Path(seconde).name).exists()
        assert client.get("/api/auth/moi").get_json()["photo_profil"] == seconde

    @pytest.mark.parametrize(
        ("contenu", "nom", "message"),
        [
            (b"MZ\x90\x00 executable", "virus.jpg", "virus.jpg : le fichier n'est pas une image valide (jpg, jpeg, png, webp)."),
            (image_jpeg(), "photo.gif", "photo.gif : format non autorisé (jpg, jpeg, png, webp)."),
        ],
        ids=["executable_renomme_en_jpg", "extension_gif"],
    )
    def test_fichier_refuse_par_les_controles_des_annonces(self, client, compte, dossier_uploads, contenu, nom, message):
        # Act
        reponse = self.envoyer(client, contenu, nom)
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json() == {"error": "validation", "details": {"photo": [message]}}
        assert not dossier_uploads.exists() or list(dossier_uploads.iterdir()) == []

    def test_echec_de_la_base_supprime_le_fichier_deja_ecrit(self, client, compte, dossier_uploads, monkeypatch):
        # Arrange
        entete = entete_csrf(client)

        def commit_en_panne():
            raise RuntimeError("panne base simulée")

        monkeypatch.setattr(db.session, "commit", commit_en_panne)
        # Act
        reponse = client.post(self.URL, data={"photo": (io.BytesIO(image_jpeg()), "moi.jpg")},
                              content_type="multipart/form-data", headers=entete)
        monkeypatch.undo()
        # Assert
        assert reponse.status_code == 500
        assert list(dossier_uploads.iterdir()) == []
        assert client.get("/api/auth/moi").get_json()["photo_profil"] is None

    def test_sans_fichier(self, client, compte):
        # Act
        reponse = client.post(self.URL, data={}, content_type="multipart/form-data", headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"photo": ["Une photo est requise."]}

    def test_suppression(self, app, client, compte, dossier_uploads):
        # Arrange
        url = self.envoyer(client, image_jpeg(), "moi.jpg").get_json()["photo_profil"]
        # Act
        reponse = client.delete(self.URL, headers=entete_csrf(client))
        encore = client.delete(self.URL, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == encore.status_code == 200
        assert reponse.get_json()["photo_profil"] is None
        assert not (dossier_uploads / Path(url).name).exists()
        assert derniere_entree(app)["details"] == {"photo_profil": {"avant": url, "apres": None}}


class TestSuppressionCompte:
    """DELETE /api/auth/moi."""

    def creer_annonce(self, client, annonce_valide, avec_photo=False):
        # USER-002 : l'annonce appartient au compte connecté du client (owner_id n'est plus envoyé).
        annonce = client.post("/api/annonces", json=annonce_valide, headers=entete_csrf(client)).get_json()
        if avec_photo:
            client.post(f"/api/annonces/{annonce['id']}/photos", data={"photos": [(io.BytesIO(image_jpeg()), "a.jpg")]},
                        content_type="multipart/form-data", headers=entete_csrf(client))
        return annonce

    def test_mot_de_passe_obligatoire(self, app, client, compte):
        # Act
        faux = client.delete("/api/auth/moi", json={"mot_de_passe": MAUVAIS_MOT_DE_PASSE}, headers=entete_csrf(client))
        absent = client.delete("/api/auth/moi", json={}, headers=entete_csrf(client))
        # Assert
        assert faux.status_code == absent.status_code == 400
        assert faux.get_json()["details"] == {"mot_de_passe": ["Mot de passe incorrect."]}
        assert client.get("/api/auth/moi").status_code == 200

    def test_supprime_compte_photo_et_annonces_du_proprietaire_en_gardant_l_historique(
        self, app, client, compte, annonce_valide, dossier_uploads, client_autre_proprietaire
    ):
        # Arrange : photo de profil, 2 annonces du compte (dont une avec photo), 1 annonce d'un autre propriétaire
        client.post("/api/auth/moi/photo", data={"photo": (io.BytesIO(image_jpeg()), "moi.jpg")},
                    content_type="multipart/form-data", headers=entete_csrf(client))
        a1 = self.creer_annonce(client, annonce_valide, avec_photo=True)
        a2 = self.creer_annonce(client, annonce_valide)
        autre = self.creer_annonce(client_autre_proprietaire, annonce_valide)
        assert len(list(dossier_uploads.iterdir())) == 2
        # Act
        reponse = client.delete("/api/auth/moi", json={"mot_de_passe": MOT_DE_PASSE}, headers=entete_csrf(client))
        # Assert
        assert reponse.status_code == 204
        assert client.get("/api/auth/moi").status_code == 401
        assert client.get(f"/api/annonces/{a1['id']}").status_code == 404
        assert client.get(f"/api/annonces/{a2['id']}").status_code == 404
        # Annonce (brouillon) de l'autre propriétaire : toujours là, visible par son propriétaire.
        assert client_autre_proprietaire.get(f"/api/annonces/{autre['id']}").status_code == 200
        assert list(dossier_uploads.iterdir()) == []
        with app.app_context():
            assert db.session.get(Utilisateur, compte["id"]) is None
            suppression = db.session.scalars(
                select(UtilisateurHistorique).where(UtilisateurHistorique.action == "suppression")
            ).one()
            assert suppression.utilisateur_id == compte["id"]
            assert suppression.details == {"role": "proprietaire", "nb_annonces_supprimees": 2}
            supprimees = db.session.scalars(
                select(AnnonceHistorique.annonce_id).where(AnnonceHistorique.action == "suppression")
            ).all()
            assert sorted(supprimees) == sorted([a1["id"], a2["id"]])
        # Le compte supprimé ne peut plus se connecter (même réponse qu'un email inconnu).
        connexion = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE})
        assert connexion.status_code == 401

    def test_suppression_en_un_seul_commit(self, client, compte, annonce_valide, monkeypatch):
        # Arrange
        self.creer_annonce(client, annonce_valide)
        self.creer_annonce(client, annonce_valide)
        entete = entete_csrf(client)
        appels = []
        commit_reel = db.session.commit

        def commit_compte():
            appels.append(1)
            return commit_reel()

        monkeypatch.setattr(db.session, "commit", commit_compte)
        # Act
        reponse = client.delete("/api/auth/moi", json={"mot_de_passe": MOT_DE_PASSE}, headers=entete)
        # Assert : compte, annonces et historique dans la même transaction
        assert reponse.status_code == 204
        assert len(appels) == 1

    def test_echec_du_commit_ne_supprime_rien(self, app, client, compte, annonce_valide, monkeypatch):
        # Arrange
        annonce = self.creer_annonce(client, annonce_valide)
        entete = entete_csrf(client)

        def commit_en_panne():
            raise RuntimeError("panne base simulée")

        monkeypatch.setattr(db.session, "commit", commit_en_panne)
        # Act
        reponse = client.delete("/api/auth/moi", json={"mot_de_passe": MOT_DE_PASSE}, headers=entete)
        monkeypatch.undo()
        # Assert : une seule transaction → ni le compte, ni l'annonce, ni l'historique ne sont supprimés
        assert reponse.status_code == 500
        with app.app_context():
            assert db.session.get(Utilisateur, compte["id"]) is not None
            assert db.session.get(Annonce, annonce["id"]) is not None
        assert client.get("/api/auth/moi").status_code == 200
