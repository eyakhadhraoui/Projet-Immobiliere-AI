from app.ia.maintenance_photo import detect_image_type, normalize_suggestion
import io
import json

from flask import Flask

from app.ia import maintenance_photo


def test_magic_bytes_acceptent_jpeg_png_webp():
    assert detect_image_type(b"\xff\xd8\xff\xe0rest") == "jpg"
    assert detect_image_type(b"\x89PNG\r\n\x1a\nrest") == "png"
    assert detect_image_type(b"RIFFxxxxWEBPrest") == "webp"
    assert detect_image_type(b"MZfake-image") is None


def test_normalize_une_suggestion_valide_et_borne_la_confiance():
    suggestion = normalize_suggestion({
        "is_maintenance_issue": True,
        "room": "cuisine",
        "urgency": "critique",
        "title": "  Fuite  ",
        "description": " Eau visible sous l'évier ",
        "confidence": 1.7,
    })
    assert suggestion == {
        "is_maintenance_issue": True,
        "room": "cuisine",
        "urgency": "critique",
        "title": "Fuite",
        "description": "Eau visible sous l'évier",
        "confidence": 1.0,
    }


def test_normalize_refuse_les_valeurs_hors_vocabulaire_et_non_incidents():
    suggestion = normalize_suggestion({
        "is_maintenance_issue": False,
        "room": "grenier",
        "urgency": "immediate",
        "title": "Paysage",
        "description": "Aucun problème visible",
        "confidence": -0.2,
    })
    assert suggestion["is_maintenance_issue"] is False
    assert suggestion["room"] is None
    assert suggestion["urgency"] is None
    assert suggestion["title"] is None
    assert suggestion["description"] is None
    assert suggestion["confidence"] == 0.0


def test_route_analyse_photo_exige_une_session(client):
    response = client.post("/api/maintenance/ia/analyze-photo", data={})
    assert response.status_code == 401


def test_analyse_envoie_image_inline_et_schema_json_avec_gemini_simule(monkeypatch):
    application = Flask(__name__)
    application.config.update(
        GEMINI_API_KEY="cle-factice-pour-test",
        GEMINI_MODEL="modele-test",
        GEMINI_TIMEOUT=3,
    )
    corps = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps({
        "is_maintenance_issue": True,
        "room": "cuisine",
        "urgency": "moyenne",
        "title": "Robinet endommagé",
        "description": "Le robinet semble abîmé.",
        "confidence": 0.91,
    })}]}]}
    appels = []

    class ReponseFausse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def urlopen_factice(req, timeout):
        appels.append((req, timeout))
        return ReponseFausse(json.dumps(corps).encode())

    monkeypatch.setattr(maintenance_photo.urllib.request, "urlopen", urlopen_factice)
    with application.app_context():
        resultat = maintenance_photo.analyze_photo(b"image-factice", "image/jpeg")

    requete, timeout = appels[0]
    corps_envoye = json.loads(requete.data)
    assert timeout == 3
    assert corps_envoye["response_format"]["mime_type"] == "application/json"
    assert corps_envoye["response_format"]["schema"] == maintenance_photo.SCHEMA
    assert corps_envoye["input"][1]["mime_type"] == "image/jpeg"
    assert corps_envoye["store"] is False
    assert requete.full_url.endswith("/v1beta/interactions")
    assert resultat["title"] == "Robinet endommagé"
