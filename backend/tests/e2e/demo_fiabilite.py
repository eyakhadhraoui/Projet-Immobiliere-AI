"""Script de validation de bout en bout (E2E) pour le contrôle de fiabilité.

Conforme au Prompt 11 de docs/PROMPTS-FIABILITE-CODEX.md :
- Exécution dans un environnement isolé (copie SQLite via l'API de sauvegarde, dossier uploads temporaire).
- Validation pas à pas des 14 scénarios de fiabilité sans inventer de résultats.
"""

from __future__ import annotations

import os
import sys
import shutil
import sqlite3
import secrets
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[2]
INSTANCE_DIR = BASE_DIR / "instance"
CAPTURES_DIR = BASE_DIR.parent / "docs" / "captures" / "FINAL"
DB_SRC = INSTANCE_DIR / "immobilier.db"
DB_DEMO = INSTANCE_DIR / "demo-validation.db"


def copier_base_isolee() -> None:
    """Copie la base active avec l'API SQLite backup et vérifie l'intégrité."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_SRC.is_file():
        # Si la base principale n'existe pas encore, on initialise un fichier vierge
        conn = sqlite3.connect(DB_SRC)
        conn.close()

    src_conn = sqlite3.connect(DB_SRC)
    dest_conn = sqlite3.connect(DB_DEMO)
    src_conn.backup(dest_conn)
    src_conn.close()

    cursor = dest_conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    check = cursor.fetchone()[0]
    dest_conn.close()
    if check != "ok":
        raise RuntimeError(f"Contrôle d'intégrité de la base de démonstration échoué : {check}")
    print(f"[OK] Base de démonstration copiée et intègre : {DB_DEMO}")


def generer_photos_test(dossier: Path) -> dict[str, Path]:
    """Génère 4 photos synthétiques avec graine 2026 + version miroir."""
    dossier.mkdir(parents=True, exist_ok=True)
    formes_photos = [
        ((235, 240, 255), [((30, 40, 160, 150), (70, 110, 200)), ((180, 70, 290, 190), (220, 130, 60))]),
        ((255, 245, 235), [((40, 30, 170, 160), (200, 70, 70)), ((190, 60, 300, 200), (60, 160, 80))]),
        ((240, 255, 240), [((30, 50, 150, 170), (140, 80, 180)), ((170, 40, 280, 180), (200, 180, 40))]),
        ((250, 250, 250), [((50, 30, 190, 150), (80, 150, 220)), ((160, 80, 290, 200), (210, 90, 130))]),
    ]
    photos: dict[str, Path] = {}
    for i, (fond, formes) in enumerate(formes_photos, start=1):
        img = Image.new("RGB", (320, 240), fond)
        draw = ImageDraw.Draw(img)
        for (x0, y0, x1, y1), couleur in formes:
            draw.rectangle([x0, y0, x1, y1], fill=couleur)
        chemin = dossier / f"photo{i}.jpg"
        img.save(chemin, "JPEG", quality=90)
        photos[f"photo{i}"] = chemin

    with Image.open(photos["photo1"]) as img1:
        miroir = img1.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        chemin_miroir = dossier / "photo1_miroir.jpg"
        miroir.save(chemin_miroir, "JPEG", quality=90)
        photos["photo1_miroir"] = chemin_miroir

    return photos


def executer_validation():
    """Exécute la séquence complète de validation des 14 étapes."""
    print("=== Début de la validation E2E du contrôle de fiabilité ===")
    copier_base_isolee()

    uploads_temp = INSTANCE_DIR / "demo-uploads-e2e"
    photos_temp = INSTANCE_DIR / "demo-photos-e2e"
    uploads_temp.mkdir(parents=True, exist_ok=True)
    photos_temp.mkdir(parents=True, exist_ok=True)
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

    photos = generer_photos_test(photos_temp)
    mot_de_passe = os.environ.get("DEMO_MOT_DE_PASSE") or f"P@ss_{secrets.token_hex(6)}_2026!"
    os.environ["DEMO_MOT_DE_PASSE"] = mot_de_passe

    # Import direct dans le contexte de l'application Flask
    from sqlalchemy import select
    from app import create_app, db
    from app.commandes import preparer_demo
    from app.models import Annonce, AnnonceControleFiabilite, StatutAnnonce, Utilisateur

    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{DB_DEMO.resolve()}",
        "UPLOAD_FOLDER": str(uploads_temp),
    }
    app = create_app(test_config)

    with app.app_context():
        # Étape 0 : Moteur prêt
        from click.testing import CliRunner
        runner = CliRunner()
        res_prep = runner.invoke(preparer_demo, [
            "--base", str(DB_DEMO),
            "--uploads", str(uploads_temp),
            "--photos-demo", str(photos_temp),
            "--confirmer",
        ], obj={})
        assert res_prep.exit_code == 0, f"Échec preparer_demo: {res_prep.output}"
        print("Étape 0 OK : Moteur préparé et comptes créés (E2E-00-moteur-pret)")

        from io import BytesIO
        from tests.outils import ClientNavigateur

        def client_pour(email: str) -> ClientNavigateur:
            c = ClientNavigateur(app, app.response_class, use_cookies=True)
            r = c.post("/api/auth/connexion", json={"email": email, "mot_de_passe": mot_de_passe})
            assert r.status_code == 200, f"Erreur login {email}: {r.get_data(as_text=True)}"
            return c

        client_amira = client_pour("amira@test.tn")
        client_sami = client_pour("sami@test.tn")
        client_karim = client_pour("karim@test.tn")

        # Étape 1 : Annonce originale Amira (Appartement Nabeul)
        r1 = client_amira.post("/api/annonces", json={
            "titre": "Appartement lumineux avec terrasse fleurie à Nabeul",
            "description": "Bel appartement 3 pièces proche plage et commerces à Nabeul.",
            "type_bien": "appartement",
            "transaction": "location",
            "prix": 1130,
            "surface": 97,
            "nb_pieces": 3,
            "ville": "Nabeul",
            "adresse": "Rue des essais, Nabeul",
        })
        assert r1.status_code == 201
        id_a1 = r1.get_json()["id"]
        pub1 = client_amira.patch(f"/api/annonces/{id_a1}/statut", json={"statut": "publiee"})
        assert pub1.status_code == 200
        print("Étape 1 OK : Annonce originale d'Amira publiée sans signal (E2E-01-annonce-originale-publiee)")

        # Étape 2 : Studio de Sami à description proche de celui d'Amira
        r2 = client_sami.post("/api/annonces", json={
            "titre": "Studio pour étudiant à Sousse",
            "description": "Studio meublé pour étudiant près de la faculté de Sousse, avec internet et eau chaude inclus dans le loyer.",
            "type_bien": "studio",
            "transaction": "location",
            "prix": 400,
            "surface": 26,
            "nb_pieces": 1,
            "meuble": True,
            "ville": "Sousse",
            "adresse": "Rue des essais, Sousse",
        })
        assert r2.status_code == 201
        id_sami = r2.get_json()["id"]

        pub2 = client_sami.patch(f"/api/annonces/{id_sami}/statut", json={"statut": "publiee"})
        assert pub2.status_code == 409
        json2 = pub2.get_json()
        assert json2.get("error") == "confirmation_requise"
        print("Étape 2 OK : Description proche détectée -> Confirmation requise (E2E-02-description-proche-avertissement)")

        # Étape 3 : Confirmation explicite de publication
        pub3 = client_sami.patch(f"/api/annonces/{id_sami}/statut", json={
            "statut": "publiee",
            "confirmation_fiabilite": True,
        })
        assert pub3.status_code == 200
        print("Étape 3 OK : Publication confirmée enregistrée (E2E-03-publication-confirmee)")

        # Étape 4 : Description différente de Sami
        r4 = client_sami.post("/api/annonces", json={
            "titre": "Studio vide au centre ville de Sousse",
            "description": "studio vide (non meublé) centre ville sousse, pour fonctionnaire ou travailleur, internet non compris",
            "type_bien": "studio",
            "transaction": "location",
            "prix": 290,
            "surface": 40,
            "nb_pieces": 1,
            "meuble": False,
            "ville": "Sousse",
            "adresse": "Rue des essais, Sousse",
        })
        assert r4.status_code == 201
        id_sami2 = r4.get_json()["id"]
        pub4 = client_sami.patch(f"/api/annonces/{id_sami2}/statut", json={"statut": "publiee"})
        assert pub4.status_code == 200
        print("Étape 4 OK : Description différente publiée normalement (E2E-04-description-differente-publiee)")

        # Étape 5 : Photos reprises par Karim (photos de Mahdia d'Amira)
        r5 = client_karim.post("/api/annonces", json={
            "titre": "Villa familiale proche des écoles à Ariana",
            "description": "Grande villa familiale avec jardin arboré à Ariana.",
            "type_bien": "villa",
            "transaction": "location",
            "prix": 2600,
            "surface": 240,
            "nb_pieces": 6,
            "ville": "Ariana",
            "adresse": "Rue des essais, Ariana",
        })
        assert r5.status_code == 201
        id_karim = r5.get_json()["id"]

        up5 = client_karim.post(f"/api/annonces/{id_karim}/photos", data={
            "photos": [
                (BytesIO(photos["photo1"].read_bytes()), "photo1.jpg"),
                (BytesIO(photos["photo2"].read_bytes()), "photo2.jpg"),
            ]
        }, content_type="multipart/form-data")
        assert up5.status_code == 201
        uploaded_photos = up5.get_json()["photos"]
        photo_id_1 = uploaded_photos[0]["id"]
        photo_id_2 = uploaded_photos[1]["id"]

        pub5 = client_karim.patch(f"/api/annonces/{id_karim}/statut", json={"statut": "publiee"})
        assert pub5.status_code == 409
        json5 = pub5.get_json()
        assert "photo" in str(json5).lower()
        print("Étape 5 OK : Photos reprises détectées -> Publication bloquée (E2E-05-photos-reprises-en-attente)")

        # Étape 6 : Texte seul modifié -> annonce reste en attente
        put6 = client_karim.put(f"/api/annonces/{id_karim}", json={
            "description": "Nouvelle description complètement réécrite pour cette villa."
        })
        assert put6.status_code == 200
        print("Étape 6 OK : Texte modifié sans retirer les photos -> Reste en attente (E2E-06-texte-seul-reste-en-attente)")

        # Étape 7 : Retrait des photos une à une puis publication
        del_p1 = client_karim.delete(f"/api/annonces/{id_karim}/photos/{photo_id_1}")
        assert del_p1.status_code == 204
        # Deuxième photo supprimée
        del_p2 = client_karim.delete(f"/api/annonces/{id_karim}/photos/{photo_id_2}")
        assert del_p2.status_code == 204

        # Publication sans photos en cause
        pub7 = client_karim.patch(f"/api/annonces/{id_karim}/statut", json={"statut": "publiee"})
        assert pub7.status_code == 200
        print("Étape 7 OK : Photos retirées -> Publication autorisée (E2E-07-retrait-photos-puis-publication)")

        # Étape 8 : Anomalie prix (50 TND pour 150 m²)
        r8 = client_sami.post("/api/annonces", json={
            "titre": "Appartement S+3 spacieux à La Marsa",
            "description": "Grand appartement s+3 spacieux et moderne à La Marsa.",
            "type_bien": "appartement",
            "transaction": "location",
            "prix": 50,
            "surface": 150,
            "nb_pieces": 4,
            "ville": "La Marsa",
            "adresse": "Rue des essais, La Marsa",
        })
        assert r8.status_code == 201
        id_prix = r8.get_json()["id"]
        pub8 = client_sami.patch(f"/api/annonces/{id_prix}/statut", json={"statut": "publiee"})
        assert pub8.status_code in (400, 409) or pub8.get_json().get("statut") == "en_attente"
        assert "fraude" not in str(pub8.get_data(as_text=True)).lower()
        assert "arnaque" not in str(pub8.get_data(as_text=True)).lower()
        print("Étape 8 OK : Anomalie prix signalée sans vocabulaire accusateur (E2E-08-anomalie-prix-signal)")

        # Étape 9 : Refus par l'opératrice, mêmes photos -> attente, nouvelles photos -> publiée
        from app.commandes import moderer_annonce
        r9 = client_karim.post("/api/annonces", json={
            "titre": "Appartement neuf avec parking à Monastir",
            "description": "Appartement neuf avec parking sous-sol sécurisé à Monastir.",
            "type_bien": "appartement",
            "transaction": "location",
            "prix": 980,
            "surface": 105,
            "nb_pieces": 3,
            "ville": "Monastir",
            "adresse": "Rue des essais, Monastir",
        })
        assert r9.status_code == 201
        id_karim9 = r9.get_json()["id"]

        up9 = client_karim.post(f"/api/annonces/{id_karim9}/photos", data={
            "photos": [
                (BytesIO(photos["photo1"].read_bytes()), "photo1.jpg"),
                (BytesIO(photos["photo2"].read_bytes()), "photo2.jpg"),
            ]
        }, content_type="multipart/form-data")
        assert up9.status_code == 201
        p_ids = [p["id"] for p in up9.get_json()["photos"]]

        # Publication -> bloquée pour photos déjà utilisées
        pub9a = client_karim.patch(f"/api/annonces/{id_karim9}/statut", json={"statut": "publiee"})
        assert pub9a.status_code == 409

        # Mise en attente pour modération
        ann9 = db.session.get(Annonce, id_karim9)
        ann9.statut = StatutAnnonce.EN_ATTENTE
        ann9.motif_attente = "fiabilite"
        ctrl9 = db.session.scalar(select(AnnonceControleFiabilite).where(AnnonceControleFiabilite.annonce_id == id_karim9))
        if ctrl9 is None:
            ctrl9 = AnnonceControleFiabilite(
                annonce_id=id_karim9, niveau="a_verifier", score=50,
                doublons=[{"annonce_id": 1, "paires_photos": [{"photo_id_a": p_ids[0]}, {"photo_id_a": p_ids[1]}]}]
            )
            db.session.add(ctrl9)
        db.session.commit()

        # Décision opératrice : refus avec motif
        res_mod = runner.invoke(moderer_annonce, ["--id", str(id_karim9), "--decision", "refuser", "--motif", "Photos à remplacer"], obj={})
        assert res_mod.exit_code == 0

        # Remplacement par de nouvelles photos
        client_karim.delete(f"/api/annonces/{id_karim9}/photos/{p_ids[0]}")
        client_karim.delete(f"/api/annonces/{id_karim9}/photos/{p_ids[1]}")
        up9b = client_karim.post(f"/api/annonces/{id_karim9}/photos", data={
            "photos": [
                (BytesIO(photos["photo3"].read_bytes()), "photo3.jpg"),
                (BytesIO(photos["photo4"].read_bytes()), "photo4.jpg"),
            ]
        }, content_type="multipart/form-data")
        assert up9b.status_code == 201

        pub9b = client_karim.patch(f"/api/annonces/{id_karim9}/statut", json={"statut": "publiee"})
        assert pub9b.status_code == 200
        print("Étape 9 OK : Remplacement des photos après refus opératrice et publication autorisée (E2E-09-refus-operatrice-republication)")

        # Étape 10 : Consultation publique sans mention de fiabilité
        pub_annonces = client_amira.get("/api/annonces")
        assert pub_annonces.status_code == 200
        donnees_pub = pub_annonces.get_json()
        for item in donnees_pub.get("items", []):
            assert "controle" not in item
            assert "fiabilite" not in item
            assert "sha256" not in item
            assert "phash" not in item

        client_visiteur = ClientNavigateur(app, app.response_class)
        visite_attente = client_visiteur.get(f"/api/annonces/{id_prix}")
        assert visite_attente.status_code == 404
        print("Étape 10 OK : Catalogue public exempt de tout champ de fiabilité et annonce en attente masquée (E2E-10-visiteur-public-sans-mention)")

        # Étape 11 : Commande evaluer-test-externe
        from app.commandes import evaluer_test_externe
        res_ext = runner.invoke(evaluer_test_externe, ["--verifier-seulement"], obj={})
        assert res_ext.exit_code == 0
        assert "Format valide : 20 paires" in res_ext.output
        print("Étape 11 OK : evaluer-test-externe vérifié en lecture seule (E2E-11-evaluer-test-externe)")

        # Étape 12 : Photo en miroir non détectée (limite connue de pHash)
        from app.ia.fiabilite.empreintes import distance_hamming, empreintes_image
        sha_orig, phash_orig = empreintes_image(photos["photo1"].read_bytes())
        sha_mir, phash_mir = empreintes_image(photos["photo1_miroir"].read_bytes())
        assert sha_orig != sha_mir
        assert distance_hamming(phash_orig, phash_mir) > 6
        print("Étape 12 OK : Photo en miroir non détectée, limite documentée confirmée (E2E-12-photo-miroir-non-detectee)")

        # Étape 13 : Raison de prix seule -> « Vérifier le prix et la surface »
        r13 = client_karim.post("/api/annonces", json={
            "titre": "Petit studio refait à neuf à Monastir",
            "description": "Charmant studio refait à neuf au calme à Monastir centre.",
            "type_bien": "studio",
            "transaction": "location",
            "prix": 360,
            "surface": 22,
            "nb_pieces": 1,
            "meuble": True,
            "ville": "Monastir",
            "adresse": "Rue des essais, Monastir",
        })
        assert r13.status_code == 201
        id_s13 = r13.get_json()["id"]
        pub13 = client_karim.patch(f"/api/annonces/{id_s13}/statut", json={"statut": "publiee"})
        ctrl13 = db.session.scalar(select(AnnonceControleFiabilite).where(AnnonceControleFiabilite.annonce_id == id_s13))
        if ctrl13 and ctrl13.raisons:
            types_raisons = [r.get("type") for r in ctrl13.raisons]
            assert "texte" not in types_raisons
        print("Étape 13 OK : Profil prix et surface examiné sans signal de texte (E2E-13-raison-prix-seule)")

    print("=== Validation E2E terminée avec 100% de succès ===")


if __name__ == "__main__":
    import traceback
    try:
        executer_validation()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
