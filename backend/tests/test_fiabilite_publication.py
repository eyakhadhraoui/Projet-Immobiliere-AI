"""Tests des décisions de fiabilité au changement de statut."""

from io import BytesIO

from PIL import Image

from app.ia.fiabilite import VERSION


def resultat(niveau: str, score: int, doublons=None):
    decision = {"aucun_signal": "publication_normale", "a_surveiller": "confirmation_requise",
                "a_verifier": "mise_en_attente"}[niveau]
    return {"niveau": niveau, "score": score, "raisons": [], "doublons": doublons or [],
            "decision": decision, "modele_texte": "tfidf", "version": VERSION}


def photo_jpeg(nom: str = "preuve.jpg"):
    image = Image.new("RGB", (40, 40), color="navy")
    fichier = BytesIO()
    image.save(fichier, format="JPEG")
    fichier.seek(0)
    return fichier, nom


def test_publication_normale_passe_et_le_json_public_ne_contient_pas_le_controle(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: resultat("aucun_signal", 0))
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    client_proprietaire.post(
        f"/api/annonces/{created['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    )
    response = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"})
    assert response.status_code == 200
    assert response.get_json()["statut"] == "publiee"
    public = client_proprietaire.get(f"/api/annonces/{created['id']}").get_json()
    assert "motif_attente" not in public
    assert "empreintes_refusees" not in public
    assert "fiabilite" not in public
    assert public["photos"]
    for photo in public["photos"]:
        assert "sha256" not in photo
        assert "phash" not in photo


def test_detail_proprietaire_expose_seulement_les_champs_attente_autorises(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: resultat("a_verifier", 60))
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    client_proprietaire.patch(
        f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"}
    )
    detail = client_proprietaire.get(f"/api/annonces/{created['id']}").get_json()
    assert detail["motif_attente"] == "fiabilite"
    assert detail["revue_demandee_le"] is None
    assert "empreintes_refusees" not in detail
    assert "fiabilite" not in detail


def test_confirmation_est_requise_puis_enregistree(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: resultat("a_surveiller", 25))
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    response = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"})
    assert response.status_code == 409
    assert response.get_json()["error"] == "confirmation_requise"
    confirmed = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut",
                                          json={"statut": "publiee", "confirmation_fiabilite": True})
    assert confirmed.status_code == 200
    assert confirmed.get_json()["statut"] == "publiee"


def test_niveau_a_verifier_met_en_attente_et_verrouille_le_statut(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: resultat("a_verifier", 60))
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    response = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"})
    assert response.status_code == 200
    assert response.get_json()["statut"] == "en_attente"
    assert response.get_json()["motif_attente"] == "fiabilite"
    verrou = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut", json={"statut": "brouillon"})
    assert verrou.status_code == 403
    revue = client_proprietaire.post(f"/api/annonces/{created['id']}/fiabilite/revue", json={})
    assert revue.status_code == 202


def test_modification_annonce_en_attente_recontrole_et_revient_en_brouillon_si_signal_leve(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    resultats = iter([resultat("a_verifier", 60), resultat("aucun_signal", 0)])
    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: next(resultats))
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    pending = client_proprietaire.patch(
        f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"}
    )
    assert pending.get_json()["statut"] == "en_attente"

    response = client_proprietaire.put(
        f"/api/annonces/{created['id']}", json={"description": "Description corrigée et spécifique."}
    )
    assert response.status_code == 200
    assert response.get_json()["statut"] == "brouillon"
    assert response.get_json()["motif_attente"] is None
    historique = client_proprietaire.get(f"/api/annonces/{created['id']}/historique").get_json()
    actions = [entree["action"] for entree in historique["items"]]
    assert "nouvelle_tentative" in actions
    assert "attente_levee" in actions


def test_texte_seul_ne_leve_pas_attente_si_photo_en_cause_est_toujours_presente(
    app, client_proprietaire, annonce_valide, monkeypatch
):
    from app import db
    from app.models import Annonce, AnnonceControleFiabilite, StatutAnnonce
    from app.routes import annonces as routes

    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    ajout = client_proprietaire.post(
        f"/api/annonces/{created['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    )
    photo_id = ajout.get_json()["photos"][0]["id"]
    blocage = resultat("a_verifier", 60, [{"annonce_id": 999, "points": 60,
        "signaux": ["photos_proches"], "raisons": [],
        "paires_photos": [{"photo_id_a": photo_id, "photo_id_b": 1, "distance": 0, "identique": True}]}])
    with app.app_context():
        annonce = db.session.get(Annonce, created["id"])
        annonce.statut = StatutAnnonce.EN_ATTENTE
        annonce.motif_attente = "fiabilite"
        db.session.add(AnnonceControleFiabilite(
            annonce_id=annonce.id, niveau="a_verifier", score=60, raisons=[],
            doublons=blocage["doublons"], decision="mise_en_attente",
            modele_texte="tfidf", version=VERSION,
        ))
        db.session.commit()
    resultats = iter([resultat("aucun_signal", 0)])
    appels = []

    def analyser(*args):
        appels.append(1)
        return next(resultats)

    monkeypatch.setattr(routes, "analyser_annonce", analyser)
    modification = client_proprietaire.put(
        f"/api/annonces/{created['id']}", json={"description": "Description modifiée seulement."}
    )
    assert modification.get_json()["statut"] == "en_attente"
    assert "photos identiques sont toujours présentes" in modification.get_json()["message_fiabilite"]
    assert modification.get_json()["photos_encore_en_cause"] == [1]
    assert len(appels) == 0

    retrait = client_proprietaire.delete(f"/api/annonces/{created['id']}/photos/{photo_id}")
    assert retrait.status_code == 200
    assert retrait.get_json()["motif_attente"] is None
    assert len(appels) == 1


def test_photo_refusee_precedemment_redeclenche_une_mise_en_attente(
    app, client_proprietaire, annonce_valide
):
    from app import db
    from app.ia.fiabilite.service import analyser_annonce
    from app.models import Annonce, AnnoncePhoto

    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    ajout = client_proprietaire.post(
        f"/api/annonces/{created['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    )
    photo_id = ajout.get_json()["photos"][0]["id"]
    with app.app_context():
        photo = db.session.get(AnnoncePhoto, photo_id)
        annonce = db.session.get(Annonce, created["id"])
        annonce.empreintes_refusees = [{"sha256": photo.sha256, "phash": photo.phash}]
        db.session.commit()
        resultat_controle = analyser_annonce(annonce, app.config["MODELES_FOLDER"])
    assert resultat_controle["niveau"] == "a_verifier"
    assert any(r["signal"] == "photo_deja_refusee" for r in resultat_controle["raisons"])


def test_photo_deja_publiee_bloque_la_publication_meme_avec_confirmation(
    client_proprietaire, annonce_valide, monkeypatch
):
    from app.ia.fiabilite.service import analyser_annonce as analyser_reel
    from app.routes import annonces as routes

    originale = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    client_proprietaire.post(
        f"/api/annonces/{originale['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    )
    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: resultat("aucun_signal", 0))
    publiee = client_proprietaire.patch(
        f"/api/annonces/{originale['id']}/statut", json={"statut": "publiee"}
    )
    assert publiee.status_code == 200

    copie = client_proprietaire.post("/api/annonces", json={
        **annonce_valide,
        "titre": "Même bien avec une autre description",
        "description": "Description réécrite pour l'annonce du même propriétaire.",
    }).get_json()
    client_proprietaire.post(
        f"/api/annonces/{copie['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    )
    monkeypatch.setattr(routes, "analyser_annonce", analyser_reel)

    reponse = client_proprietaire.patch(
        f"/api/annonces/{copie['id']}/statut", json={"statut": "publiee"}
    )
    assert reponse.status_code == 409
    assert reponse.get_json()["error"] == "photos_deja_utilisees"
    assert "Publication bloquée" in reponse.get_json()["message"]
    assert reponse.get_json()["photos_a_remplacer"] == [1]
    assert client_proprietaire.get(f"/api/annonces/{copie['id']}").get_json()["statut"] == "brouillon"

    confirmation = client_proprietaire.patch(
        f"/api/annonces/{copie['id']}/statut",
        json={"statut": "publiee", "confirmation_fiabilite": True},
    )
    assert confirmation.status_code == 409
    assert confirmation.get_json()["error"] == "photos_deja_utilisees"


def test_moderation_ne_peut_pas_forcer_la_publication_d_une_photo_detectee(
    app, client_proprietaire, annonce_valide
):
    from app import db
    from app.models import Annonce, AnnonceControleFiabilite, StatutAnnonce

    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    photo = client_proprietaire.post(
        f"/api/annonces/{created['id']}/photos",
        data={"photos": photo_jpeg()}, content_type="multipart/form-data",
    ).get_json()["photos"][0]
    with app.app_context():
        annonce = db.session.get(Annonce, created["id"])
        annonce.statut = StatutAnnonce.EN_ATTENTE
        annonce.motif_attente = "fiabilite"
        db.session.add(AnnonceControleFiabilite(
            annonce_id=annonce.id, niveau="a_verifier", score=60, raisons=[],
            doublons=[{"annonce_id": 999, "points": 50, "signaux": ["photos_proches"],
                       "paires_photos": [{"photo_id_a": photo["id"], "photo_id_b": 1,
                                          "distance": 0, "identique": True}]}],
            decision="mise_en_attente", modele_texte="tfidf", version=VERSION,
        ))
        db.session.commit()

    reponse = app.test_cli_runner().invoke(args=[
        "moderer-annonce", "--id", str(created["id"]), "--decision", "publier", "--motif", "Contrôle"
    ])
    assert reponse.exit_code == 1
    assert "Publication bloquée" in reponse.output
    with app.app_context():
        annonce = db.session.get(Annonce, created["id"])
        assert annonce.statut == StatutAnnonce.EN_ATTENTE


def test_route_fiabilite_n_est_pas_accessible_aux_autres_comptes(
    client_proprietaire, client_autre_proprietaire, annonce_valide
):
    created = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    response = client_autre_proprietaire.get(f"/api/annonces/{created['id']}/fiabilite")
    assert response.status_code == 403


def test_correspondance_privee_ne_divulgue_pas_identifiant_ni_titre(
    app, client_proprietaire, client_autre_proprietaire, annonce_valide, monkeypatch
):
    from app.routes import annonces as routes

    privee = client_autre_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    matching = resultat("a_verifier", 60, [{"annonce_id": privee["id"], "points": 50,
        "signaux": ["photos_proches"], "raisons": [], "paires_photos": []}])
    monkeypatch.setattr(routes, "analyser_annonce", lambda *_: matching)
    created = client_proprietaire.post("/api/annonces", json={**annonce_valide, "titre": "Mon annonce distincte"}).get_json()
    response = client_proprietaire.patch(f"/api/annonces/{created['id']}/statut", json={"statut": "publiee"})
    assert response.status_code == 200
    lien = response.get_json()["fiabilite"]["annonces_liees"][0]
    assert lien["annonce"] == "une autre annonce"
    assert "annonce_id" not in lien
    assert privee["titre"] not in response.get_data(as_text=True)
