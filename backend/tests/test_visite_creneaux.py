"""Tests de proposition et de réservation atomique des créneaux."""

from datetime import datetime, timedelta

from app import db
from app.models import DisponibiliteVisite


def test_creneaux_proposes_et_recontrole_du_chevauchement(
    app, client_proprietaire, annonce_valide
):
    """Un créneau proposé ne peut pas être réservé deux fois."""
    annonce = client_proprietaire.post("/api/annonces", json=annonce_valide).get_json()
    assert client_proprietaire.patch(
        f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"}
    ).status_code == 200

    jour = (datetime.now() + timedelta(days=1)).weekday() + 1
    with app.app_context():
        db.session.add(DisponibiliteVisite(
            annonce_id=annonce["id"],
            jour_semaine=jour,
            heure_debut="09:00",
            heure_fin="10:30",
            actif=True,
        ))
        db.session.commit()

    response = client_proprietaire.get(f"/api/annonces/{annonce['id']}/creneaux")
    assert response.status_code == 200
    creneau = response.get_json()["creneaux"][0]
    donnees = {
        "annonce_id": annonce["id"],
        "date_visite": creneau["date"],
        "heure_debut": creneau["heure_debut"],
        "heure_fin": creneau["heure_fin"],
        "telephone_contact": "98123456",
    }
    assert client_proprietaire.post("/api/visites", json=donnees).status_code == 201
    seconde = client_proprietaire.post("/api/visites", json=donnees)
    assert seconde.status_code == 409
    assert seconde.get_json()["error"] == "creneau_indisponible"
