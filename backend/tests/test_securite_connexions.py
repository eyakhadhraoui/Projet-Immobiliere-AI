"""Tests du module de détection des connexions inhabituelles."""

from datetime import datetime, timedelta, timezone

from app import db
from app.models import EvenementConnexion, Utilisateur, VerificationConnexion
from tests.outils import MOT_DE_PASSE, entete_csrf


def _connexion(client, compte, user_agent="Mozilla/5.0 Chrome/120.0 Windows NT 10.0"):
    client.post("/api/auth/deconnexion")
    return client.post("/api/auth/connexion", json={
        "email": compte["email"], "mot_de_passe": MOT_DE_PASSE,
    }, headers={"User-Agent": user_agent})


def test_connexion_normale_est_enregistree_sans_defi(app, client, compte):
    reponse = _connexion(client, compte)
    assert reponse.status_code == 200
    assert reponse.get_json()["id"] == compte["id"]
    assert "access_token_cookie" in reponse.headers.get("Set-Cookie", "")
    with app.app_context():
        evenement = db.session.query(EvenementConnexion).filter_by(utilisateur_id=compte["id"], reussie=True).one()
        assert evenement.navigateur == "Chrome"
        assert evenement.appareil == "ordinateur"
        assert evenement.ip_hash


def test_connexion_tres_suspecte_exige_code_et_code_usage_une_fois(app, client, compte, monkeypatch):
    from app.services import securite_connexion_service

    codes = []
    monkeypatch.setattr(securite_connexion_service, "envoyer_code", lambda utilisateur, code: codes.append(code))
    with app.app_context():
        for _ in range(4):
            db.session.add(EvenementConnexion(
                utilisateur_id=compte["id"], reussie=False,
                heure_utc=datetime.now(timezone.utc) - timedelta(minutes=2),
                navigateur="Chrome", appareil="ordinateur", ip_hash="ancienne-empreinte",
            ))
        db.session.commit()

    reponse = _connexion(client, compte)
    assert reponse.status_code == 202
    donnees = reponse.get_json()
    assert donnees["verification_requise"] is True
    assert client.get_cookie("access_token_cookie") is None
    assert len(codes) == 1

    validation = client.post("/api/auth/verification-connexion", json={
        "jeton": donnees["jeton_verification"], "code": codes[0],
    })
    assert validation.status_code == 200
    assert validation.get_json()["id"] == compte["id"]
    replay = client.post("/api/auth/verification-connexion", json={
        "jeton": donnees["jeton_verification"], "code": codes[0],
    })
    assert replay.status_code == 401
    with app.app_context():
        assert db.session.query(VerificationConnexion).one().utilise_le is not None


def test_retour_utilisateur_confirme_et_refuse(app, client, compte):
    from app.services.securite_connexion_service import empreinte

    with app.app_context():
        utilisateur = db.session.get(Utilisateur, compte["id"])
        db.session.add(EvenementConnexion(
            utilisateur_id=utilisateur.id, reussie=True,
            heure_utc=datetime.now(timezone.utc) - timedelta(days=1),
            navigateur="Chrome", appareil="ordinateur", ip_hash=empreinte("10.0.0.1"),
        ))
        db.session.commit()

    reponse = _connexion(client, compte, "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Firefox/120.0")
    assert reponse.status_code == 200
    evenement_id = reponse.get_json()["alerte_connexion"]["evenement_id"]
    confirmee = client.post(f"/api/auth/connexions/{evenement_id}/retour", json={"retour": "confirmee"},
                            headers=entete_csrf(client))
    assert confirmee.status_code == 200
    with app.app_context():
        evenement = db.session.get(EvenementConnexion, evenement_id)
        assert evenement.retour_utilisateur == "confirmee"

    # Une seconde connexion inhabituelle est contestée; la version JWT est alors révoquée.
    with app.app_context():
        db.session.add(EvenementConnexion(
            utilisateur_id=compte["id"], reussie=True,
            heure_utc=datetime.now(timezone.utc) - timedelta(days=1),
            navigateur="Chrome", appareil="ordinateur", ip_hash=empreinte("10.0.0.1"),
        ))
        db.session.commit()
    nouvelle = _connexion(client, compte, "Mozilla/5.0 Chrome/120.0 Windows NT 10.0")
    evenement_id = nouvelle.get_json()["alerte_connexion"]["evenement_id"]
    refusee = client.post(f"/api/auth/connexions/{evenement_id}/retour", json={"retour": "refusee"},
                           headers=entete_csrf(client))
    assert refusee.status_code == 200
    assert client.get("/api/auth/moi").status_code == 401
    with app.app_context():
        assert db.session.get(EvenementConnexion, evenement_id).retour_utilisateur == "refusee"
