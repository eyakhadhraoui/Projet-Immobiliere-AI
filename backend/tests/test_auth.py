"""Tests de l'authentification : inscription, connexion, blocage, session (cookies, CSRF), déconnexion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import create_app, db
from app.models import ActionUtilisateur, TentativeConnexion, Utilisateur, UtilisateurHistorique
from tests.outils import MAUVAIS_MOT_DE_PASSE, MOT_DE_PASSE, entete_csrf

NON_AUTHENTIFIE = {"error": "non_authentifie", "message": "Veuillez vous connecter."}
IDENTIFIANTS_INVALIDES = {"error": "identifiants_invalides", "message": "Email ou mot de passe incorrect."}
BLOQUE = {"error": "trop_de_tentatives", "message": "Trop de tentatives de connexion. Réessayez dans 15 minutes."}


def historique(app, action=None):
    """Entrées de l'historique des utilisateurs (de la plus ancienne à la plus récente)."""
    with app.app_context():
        requete = select(UtilisateurHistorique).order_by(UtilisateurHistorique.id)
        if action is not None:
            requete = requete.where(UtilisateurHistorique.action == action)
        return [entree.to_dict() for entree in db.session.scalars(requete)]


def cookies_poses(reponse) -> dict[str, str]:
    """En-têtes Set-Cookie de la réponse, indexés par nom de cookie."""
    return {entete.split("=", 1)[0]: entete for entete in reponse.headers.getlist("Set-Cookie")}


class TestInscription:
    """POST /api/auth/inscription."""

    def test_cree_le_compte_et_ouvre_la_session(self, client, donnees_inscription):
        # Act
        reponse = client.post("/api/auth/inscription", json={**donnees_inscription, "email": "  Loujain@Example.COM "})
        # Assert
        assert reponse.status_code == 201
        compte = reponse.get_json()
        assert compte["email"] == "loujain@example.com"
        assert compte["role"] == "proprietaire"
        assert compte["cin_numero"] == "******78"
        assert compte["cin_verifiee"] is False and compte["visage_verifie"] is False
        assert compte["created_at"].endswith("+00:00")
        assert "mot_de_passe" not in compte and "mot_de_passe_hash" not in compte
        assert "12345678" not in reponse.get_data(as_text=True)
        # Jetons en cookies httpOnly ; le jeton CSRF reste lisible par JavaScript (double cookie).
        cookies = cookies_poses(reponse)
        assert "HttpOnly" in cookies["access_token_cookie"] and "SameSite=Lax" in cookies["access_token_cookie"]
        assert "HttpOnly" in cookies["refresh_token_cookie"]
        assert "HttpOnly" not in cookies["csrf_access_token"]
        assert client.get("/api/auth/moi").status_code == 200

    def test_le_mot_de_passe_est_hache(self, app, client, donnees_inscription):
        # Act
        client.post("/api/auth/inscription", json=donnees_inscription)
        # Assert
        with app.app_context():
            utilisateur = db.session.scalar(select(Utilisateur))
            assert utilisateur.mot_de_passe_hash != MOT_DE_PASSE
            assert utilisateur.mot_de_passe_hash.startswith("scrypt:")
            assert utilisateur.verifier_mot_de_passe(MOT_DE_PASSE)

    def test_role_client_par_defaut_et_historique(self, app, client, donnees_inscription):
        # Arrange
        donnees = {k: v for k, v in donnees_inscription.items() if k != "role"}
        # Act
        compte = client.post("/api/auth/inscription", json=donnees).get_json()
        # Assert
        assert compte["role"] == "client"
        entrees = historique(app)
        assert [e["action"] for e in entrees] == ["creation"]
        assert entrees[0]["utilisateur_id"] == compte["id"]
        assert entrees[0]["details"] == {"role": "client"}

    def test_email_deja_utilise_renvoie_409(self, client, compte, donnees_inscription):
        # Act : même email, casse différente
        reponse = client.post("/api/auth/inscription", json={**donnees_inscription, "email": "LOUJAIN@example.com"})
        # Assert
        assert reponse.status_code == 409
        assert reponse.get_json() == {"error": "conflit", "message": "Un compte existe déjà avec cet email."}

    def test_cin_deja_utilisee_renvoie_409(self, client, compte, donnees_inscription):
        # Act
        reponse = client.post("/api/auth/inscription", json={**donnees_inscription, "email": "autre@example.com"})
        # Assert
        assert reponse.status_code == 409
        assert reponse.get_json()["message"] == "Cette CIN est déjà associée à un compte."

    @pytest.mark.parametrize(
        ("mot_de_passe", "message"),
        [
            ("Court1", "Doit contenir au moins 8 caractères."),
            ("sanschiffre", "Doit contenir au moins un chiffre."),
            ("12345678", "Doit contenir au moins une lettre."),
            ("a1" * 65, "Doit contenir au plus 128 caractères."),
        ],
        ids=["trop_court", "sans_chiffre", "sans_lettre", "trop_long"],
    )
    def test_politique_de_mot_de_passe(self, client, donnees_inscription, mot_de_passe, message):
        # Act
        reponse = client.post("/api/auth/inscription", json={**donnees_inscription, "mot_de_passe": mot_de_passe})
        # Assert
        assert reponse.status_code == 400
        assert message in reponse.get_json()["details"]["mot_de_passe"]

    @pytest.mark.parametrize(
        ("champ", "valeur", "message"),
        [
            ("role", "admin", "Doit être l'une des valeurs : client, proprietaire."),
            ("cin_verifiee", True, "Champ inconnu."),
            ("visage_verifie", True, "Champ inconnu."),
            ("email", "pas-un-email", "Adresse email invalide."),
            ("telephone", "abc", "Numéro de téléphone invalide."),
            ("cin_numero", "1234", "La CIN doit contenir exactement 8 chiffres."),
            ("date_naissance", "2999-01-01", "Ne peut pas être dans le futur."),
            ("date_naissance", "1899-12-31", "Date invalide."),
            ("nom", "   ", "Ce champ ne peut pas être nul."),
        ],
    )
    def test_donnees_invalides_renvoient_400(self, client, donnees_inscription, champ, valeur, message):
        # Act
        reponse = client.post("/api/auth/inscription", json={**donnees_inscription, champ: valeur})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"][champ] == [message]

    def test_corps_qui_n_est_pas_un_objet(self, client):
        # Act
        reponse = client.post("/api/auth/inscription", json=["pas", "un", "objet"])
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["error"] == "validation"

    def test_inscriptions_simultanees_avec_le_meme_email(self, client, donnees_inscription, monkeypatch):
        # Arrange : la vérification préalable ne voit pas l'autre inscription (course entre deux requêtes) ;
        # c'est la contrainte d'unicité de la base qui refuse au commit.
        from app.services import utilisateur_service

        client.post("/api/auth/inscription", json=donnees_inscription)
        monkeypatch.setattr(utilisateur_service, "_valider_unicite", lambda *args, **kwargs: None)
        # Act
        meme_email = client.post("/api/auth/inscription", json={**donnees_inscription, "cin_numero": None})
        meme_cin = client.post("/api/auth/inscription", json={**donnees_inscription, "email": "autre@example.com"})
        # Assert
        assert meme_email.status_code == meme_cin.status_code == 409
        assert meme_email.get_json()["message"] == "Un compte existe déjà avec cet email."
        assert meme_cin.get_json()["message"] == "Cette CIN est déjà associée à un compte."

    def test_champs_obligatoires(self, client):
        # Act
        reponse = client.post("/api/auth/inscription", json={})
        # Assert
        assert set(reponse.get_json()["details"]) == {"nom", "prenom", "email", "mot_de_passe"}


class TestConnexion:
    """POST /api/auth/connexion et blocage après 5 échecs."""

    def test_connexion_reussie(self, app, client, compte):
        # Arrange
        client.post("/api/auth/deconnexion")
        # Act
        reponse = client.post("/api/auth/connexion", json={"email": "LOUJAIN@example.com ", "mot_de_passe": MOT_DE_PASSE})
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json()["id"] == compte["id"]
        assert reponse.get_json()["derniere_connexion"] is not None
        assert "access_token_cookie" in cookies_poses(reponse)
        assert client.get("/api/auth/moi").status_code == 200
        assert historique(app, ActionUtilisateur.CONNEXION_REUSSIE)[0]["utilisateur_id"] == compte["id"]

    def test_meme_reponse_que_l_email_existe_ou_non(self, client, compte):
        # Act
        mauvais_mot_de_passe = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        email_inconnu = client.post("/api/auth/connexion", json={"email": "inconnu@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Assert
        assert mauvais_mot_de_passe.status_code == email_inconnu.status_code == 401
        assert mauvais_mot_de_passe.get_json() == email_inconnu.get_json() == IDENTIFIANTS_INVALIDES
        assert "access_token_cookie" not in cookies_poses(mauvais_mot_de_passe)

    @pytest.mark.parametrize("email", ["loujain@example.com", "inconnu@example.com"])
    def test_blocage_apres_5_echecs_identique_pour_un_email_existant_ou_non(self, client, compte, email):
        # Act
        reponses = [client.post("/api/auth/connexion", json={"email": email, "mot_de_passe": MAUVAIS_MOT_DE_PASSE}) for _ in range(6)]
        # Assert : 4 refus, blocage au 5e, puis toujours bloqué
        assert [r.status_code for r in reponses] == [401, 401, 401, 401, 429, 429]
        assert reponses[4].get_json() == reponses[5].get_json() == BLOQUE

    def test_bon_mot_de_passe_refuse_pendant_le_blocage_puis_accepte_apres(self, app, client, compte, monkeypatch):
        from app.services import securite_connexion_service

        codes = []
        monkeypatch.setattr(securite_connexion_service, "envoyer_code", lambda utilisateur, code: codes.append(code))
        # Arrange
        for _ in range(5):
            client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Act
        pendant = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE})
        with app.app_context():  # simule la fin des 15 minutes
            tentative = db.session.get(TentativeConnexion, "loujain@example.com")
            tentative.bloque_jusqu_a = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.session.commit()
        apres = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE})
        # Assert
        assert pendant.status_code == 429
        assert apres.status_code == 202
        donnees = apres.get_json()
        assert client.post("/api/auth/verification-connexion", json={
            "jeton": donnees["jeton_verification"], "code": codes[0],
        }).status_code == 200
        with app.app_context():
            assert db.session.get(TentativeConnexion, "loujain@example.com") is None  # compteur remis à zéro

    def test_apres_un_blocage_le_compteur_repart_de_zero(self, app, client, compte):
        # Arrange : blocage, puis fin des 15 minutes
        for _ in range(5):
            client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        with app.app_context():
            db.session.get(TentativeConnexion, "loujain@example.com").bloque_jusqu_a = (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            )
            db.session.commit()
        # Act : un nouvel échec ne rebloque pas immédiatement
        reponse = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Assert
        assert reponse.status_code == 401
        with app.app_context():
            tentative = db.session.get(TentativeConnexion, "loujain@example.com")
            assert (tentative.nb_echecs, tentative.bloque_jusqu_a) == (1, None)

    def test_un_succes_remet_le_compteur_a_zero(self, app, client, compte, monkeypatch):
        from app.services import securite_connexion_service

        codes = []
        monkeypatch.setattr(securite_connexion_service, "envoyer_code", lambda utilisateur, code: codes.append(code))
        # Arrange : 4 échecs, puis un succès
        for _ in range(4):
            client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        login = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MOT_DE_PASSE})
        if login.status_code == 202:
            donnees = login.get_json()
            assert client.post("/api/auth/verification-connexion", json={
                "jeton": donnees["jeton_verification"], "code": codes[0],
            }).status_code == 200
        else:
            assert login.status_code == 200
        # Act
        reponse = client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Assert
        assert reponse.status_code == 401

    def test_un_hash_est_verifie_meme_pour_un_email_inconnu(self, client, compte, monkeypatch):
        # Arrange : on compte les vérifications de hash (le temps de réponse ne doit pas trahir l'email)
        from app.models import utilisateur as module_modele
        from app.services import utilisateur_service

        appels = []
        for module in (utilisateur_service, module_modele):
            reel = module.check_password_hash
            monkeypatch.setattr(module, "check_password_hash",
                                lambda h, m, reel=reel: appels.append(1) or reel(h, m))
        # Act
        client.post("/api/auth/connexion", json={"email": "inconnu@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Assert : une vérification dans chaque cas
        assert len(appels) == 2

    def test_echecs_historises_sans_mot_de_passe(self, app, client, compte):
        # Act
        client.post("/api/auth/connexion", json={"email": "loujain@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        client.post("/api/auth/connexion", json={"email": "inconnu@example.com", "mot_de_passe": MAUVAIS_MOT_DE_PASSE})
        # Assert
        echecs = historique(app, ActionUtilisateur.CONNEXION_ECHOUEE)
        assert [(e["utilisateur_id"], e["email"]) for e in echecs] == [
            (compte["id"], "loujain@example.com"),
            (None, "inconnu@example.com"),
        ]
        assert echecs[0]["details"] == {"raison": "identifiants_invalides", "nb_echecs": 1, "bloque": False}
        assert echecs[0]["adresse_ip"] == "127.0.0.1"
        assert MAUVAIS_MOT_DE_PASSE not in str(echecs)

    def test_champs_manquants(self, client):
        # Act
        reponse = client.post("/api/auth/connexion", json={"email": "loujain@example.com"})
        # Assert
        assert reponse.status_code == 400
        assert reponse.get_json()["details"] == {"mot_de_passe": ["Champ obligatoire."]}


class TestSession:
    """Accès sans être connecté, CSRF, rafraîchissement, déconnexion."""

    @pytest.mark.parametrize(
        ("methode", "url"),
        [
            ("get", "/api/auth/moi"),
            ("put", "/api/auth/moi"),
            ("delete", "/api/auth/moi"),
            ("put", "/api/auth/moi/mot-de-passe"),
            ("post", "/api/auth/moi/photo"),
            ("delete", "/api/auth/moi/photo"),
            ("post", "/api/auth/rafraichir"),
        ],
    )
    def test_sans_connexion_renvoie_401(self, client, methode, url):
        # Act
        reponse = getattr(client, methode)(url, json={})
        # Assert
        assert reponse.status_code == 401
        assert reponse.get_json() == NON_AUTHENTIFIE

    def test_requete_modifiante_sans_jeton_csrf_refusee(self, client, compte):
        # Act
        sans_entete = client.put("/api/auth/moi", json={"ville": "Sousse"})
        mauvais_entete = client.put("/api/auth/moi", json={"ville": "Sousse"}, headers={"X-CSRF-TOKEN": "faux"})
        # Assert
        assert sans_entete.status_code == mauvais_entete.status_code == 403
        assert sans_entete.get_json() == {"error": "csrf_invalide", "message": "Jeton CSRF manquant ou invalide."}
        assert client.get("/api/auth/moi").get_json()["ville"] == "Tunis"

    def test_jeton_falsifie_renvoie_401(self, client, compte):
        # Arrange
        client.set_cookie("access_token_cookie", "jeton.falsifie.invalide", path="/api/")
        # Act
        reponse = client.get("/api/auth/moi")
        # Assert
        assert reponse.status_code == 401
        assert reponse.get_json() == NON_AUTHENTIFIE

    def test_jeton_expire_renvoie_401(self, app, client, compte):
        # Arrange : un jeton d'accès déjà expiré
        from flask_jwt_extended import create_access_token

        with app.app_context():
            utilisateur = db.session.get(Utilisateur, compte["id"])
            jeton = create_access_token(identity=utilisateur, expires_delta=timedelta(seconds=-1))
        client.set_cookie("access_token_cookie", jeton, path="/api/")
        # Act
        reponse = client.get("/api/auth/moi")
        # Assert
        assert reponse.status_code == 401
        assert reponse.get_json() == {"error": "non_authentifie", "message": "Session expirée, veuillez vous reconnecter."}

    def test_rafraichir(self, client, compte):
        # Act
        sans_csrf = client.post("/api/auth/rafraichir")
        avec_csrf = client.post("/api/auth/rafraichir", headers=entete_csrf(client, rafraichissement=True))
        # Assert
        assert sans_csrf.status_code == 403
        assert avec_csrf.status_code == 200
        assert avec_csrf.get_json()["id"] == compte["id"]
        assert "access_token_cookie" in cookies_poses(avec_csrf)

    def test_deconnexion_efface_les_cookies(self, client, compte):
        # Act
        reponse = client.post("/api/auth/deconnexion")
        # Assert
        assert reponse.status_code == 200
        assert reponse.get_json() == {"message": "Vous êtes déconnecté."}
        assert client.get("/api/auth/moi").status_code == 401


def test_l_application_refuse_de_demarrer_sans_cle_jwt(tmp_path):
    # Act / Assert : sans JWT_SECRET_KEY, flask-jwt-extended utiliserait SECRET_KEY sans prévenir.
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY manquante"):
        create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_SECRET_KEY": None,
                    "UPLOAD_FOLDER": str(tmp_path)})
