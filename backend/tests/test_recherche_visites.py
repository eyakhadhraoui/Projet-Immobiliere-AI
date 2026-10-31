"""Recherche de visites : filtres stricts, créneaux compatibles et lien vers réservation."""

from datetime import datetime, timedelta

from app import db
from app.models import DisponibiliteVisite, RechercheVisite, Visite


def test_recherche_retient_seulement_annonces_avec_filtres_et_creneau_compatibles(
    app, client_proprietaire, annonce_valide, villa_valide, monkeypatch
):
    """Une annonce hors filtre ou sans plage disponible ne rejoint pas les résultats."""
    annonces = []
    for donnees in (annonce_valide, villa_valide):
        annonce = client_proprietaire.post("/api/annonces", json=donnees).get_json()
        assert client_proprietaire.patch(
            f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"}
        ).status_code == 200
        annonces.append(annonce)

    demain = datetime.now().astimezone().replace(tzinfo=None) + timedelta(days=1)
    debut = demain.replace(hour=9, minute=0, second=0, microsecond=0)
    fin = debut + timedelta(minutes=30)
    with app.app_context():
        db.session.add(DisponibiliteVisite(
            annonce_id=annonces[0]["id"], jour_semaine=demain.isoweekday(),
            heure_debut="09:00", heure_fin="10:00", actif=True,
        ))
        db.session.commit()

    resultat = client_proprietaire.post("/api/visites/recherche", json={
        "villes": ["la marsa", "Sousse"],
        "transaction": "location",
        "type_bien": "appartement",
        "budget_max": 1200,
        "pieces_min": 3,
        "tri": "pertinence",
        "disponibilites": [{"debut": debut.isoformat(), "fin": fin.isoformat()}],
    })
    assert resultat.status_code == 200, resultat.get_json()
    donnees = resultat.get_json()
    assert donnees["total"] == 1
    assert donnees["items"][0]["id"] == annonces[0]["id"]
    assert donnees["items"][0]["creneaux_compatibles"][0]["heure_debut"] == "09:00"
    assert donnees["tri_applique"] == "chronologique"  # modèle absent dans la base de test
    with app.app_context():
        recherche = db.session.get(RechercheVisite, donnees["recherche_id"])
        assert recherche.candidats_annonce_ids == [annonces[0]["id"]]
    creneau = donnees["items"][0]["creneaux_compatibles"][0]
    reservation = client_proprietaire.post("/api/visites", json={
        "annonce_id": annonces[0]["id"], "recherche_id": donnees["recherche_id"],
        "date_visite": creneau["date"], "heure_debut": creneau["heure_debut"],
        "heure_fin": creneau["heure_fin"], "telephone_contact": "20123456",
    })
    assert reservation.status_code == 201, reservation.get_json()
    with app.app_context():
        visite = db.session.get(Visite, reservation.get_json()["id"])
        assert visite.recherche_id == donnees["recherche_id"]
    # Simule deux requêtes ayant toutes deux passé le contrôle de disponibilité.
    monkeypatch.setattr("app.routes.visites.creneau_autorise", lambda *args: True)
    doublon = client_proprietaire.post("/api/visites", json={
        "annonce_id": annonces[0]["id"], "recherche_id": donnees["recherche_id"],
        "date_visite": creneau["date"], "heure_debut": creneau["heure_debut"],
        "heure_fin": creneau["heure_fin"], "telephone_contact": "20123456",
    })
    assert doublon.status_code == 409
    assert doublon.get_json()["error"] == "creneau_indisponible"


def test_recherche_refuse_plage_horaire_passee(client):
    """Le serveur rejette une disponibilité antérieure à l'instant courant."""
    passe = datetime.now().astimezone().replace(tzinfo=None) - timedelta(days=1)
    response = client.post("/api/visites/recherche", json={
        "disponibilites": [{"debut": passe.isoformat(), "fin": (passe + timedelta(hours=1)).isoformat()}],
    })
    assert response.status_code == 400
    assert response.get_json()["error"] == "validation"


def test_reservation_recherchee_refuse_annonce_absente_des_candidats(
    app, client_proprietaire, annonce_valide
):
    """Un identifiant de recherche ne permet pas de réserver un autre bien."""
    annonce = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    with app.app_context():
        recherche = RechercheVisite(
            criteres={}, candidats_annonce_ids=[], methode_classement="chronologique_demande",
        )
        db.session.add(recherche)
        db.session.commit()
        recherche_id = recherche.id
    response = client_proprietaire.post("/api/visites", json={
        "annonce_id": annonce["id"], "recherche_id": recherche_id,
        "date_visite": (datetime.now().date() + timedelta(days=1)).isoformat(),
        "heure_debut": "09:00", "heure_fin": "09:30", "telephone_contact": "20123456",
    })
    assert response.status_code == 400
    assert response.get_json()["error"] == "recherche_invalide"
