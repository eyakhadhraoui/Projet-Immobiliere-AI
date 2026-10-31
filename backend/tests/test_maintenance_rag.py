import io
import json
from pathlib import Path

from flask import Flask

from app.ia.maintenance_rag import diagnosis
from app.ia.maintenance_rag.chunker import build_chunks
from app.ia.maintenance_rag.costs import CostTable, duration_label
from app.ia.maintenance_rag.retriever import Hit

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "ia" / "maintenance_rag" / "data"


def test_guide_est_decoupe_en_23_fiches_et_2_contextes():
    chunks = build_chunks(str(DATA_DIR / "guide.pdf"))
    assert len(chunks) == 25
    assert chunks[0].id == "INTRO-URGENCE"
    assert chunks[1].id == "INTRO-SECURITE"
    assert sum(chunk.metadata.get("type") == "fiche" for chunk in chunks) == 23


def test_estimation_cout_et_duree_sont_lues_depuis_le_json():
    estimate = CostTable(DATA_DIR / "couts.json").estimate("ELEC-01")
    assert estimate["cout_min"] == 40
    assert estimate["cout_max"] == 150
    assert estimate["devise"] == "TND"
    assert estimate["duree_libelle"] == "30 min à 1 h 30"
    assert CostTable(DATA_DIR / "couts.json").estimate("AUCUNE") is None
    assert duration_label(8, 16) == "1 à 2 jours"


def test_diagnostic_recherche_trois_fiches_et_valide_la_reponse(monkeypatch):
    class FauxRetriever:
        def __init__(self):
            self.query = None
            self.k = None

        def search(self, query, k):
            self.query, self.k = query, k
            return [
                Hit("ELEC-01", "Titre fiche prise", {}, 0.12),
                Hit("ELEC-02", "Titre fiche disjoncteur", {}, 0.18),
                Hit("ELEC-03", "Titre fiche câblage", {}, 0.25),
            ]

        def context(self):
            return {"INTRO-URGENCE": "Niveaux urgence", "INTRO-SECURITE": "Règles sécurité"}

    retriever = FauxRetriever()
    prompts = []

    def faux_generate(prompt, schema):
        prompts.append(prompt)
        assert schema["properties"]["fiche_id"]["enum"] == ["ELEC-01", "ELEC-02", "ELEC-03", "AUCUNE"]
        return {
            "fiche_id": "ELEC-01",
            "cause_probable": "Connexion desserrée, à confirmer.",
            "diagnostic": "Faites contrôler la prise.",
            "actions_immediates": ["Coupez le courant si vous voyez des étincelles."],
            "urgence_recommandee": "moyenne",
            "justification_urgence": "Aucun danger immédiat n'est décrit.",
        }

    monkeypatch.setattr(diagnosis, "_generate_json", faux_generate)
    result = diagnosis.diagnose(
        retriever,
        category="electricite",
        room="cuisine",
        urgency="faible",
        title="Prise qui chauffe",
        description="La prise est chaude après utilisation.",
    )
    assert retriever.query == "Prise qui chauffe. La prise est chaude après utilisation."
    assert retriever.k == 3
    assert result["fiche_id"] == "ELEC-01"
    assert result["fiche_titre"] == "Titre fiche prise"
    assert result["urgence_recommandee"] == "moyenne"
    assert result["correspondance_faible"] is False
    assert "Règles sécurité" in prompts[0]


def test_diagnostic_hors_guide_retourne_aucune_sans_fiche(monkeypatch):
    class FauxRetriever:
        def search(self, _query, k):
            assert k == 3
            return [Hit("ELEC-01", "Fiche prise", {}, 0.4)]

        def context(self):
            return {"INTRO-URGENCE": "Urgence", "INTRO-SECURITE": "Sécurité"}

    monkeypatch.setattr(diagnosis, "_generate_json", lambda *_: {
        "fiche_id": "AUCUNE",
        "cause_probable": "Le guide ne couvre pas ce problème.",
        "diagnostic": "Demandez l'avis d'un technicien.",
        "actions_immediates": [],
        "urgence_recommandee": "faible",
        "justification_urgence": "Aucun danger décrit.",
    })
    result = diagnosis.diagnose(
        FauxRetriever(), category="autre", room="salon", urgency="faible",
        title="Problème extérieur", description="Un problème sans fiche correspondante.",
    )
    assert result["fiche_id"] == "AUCUNE"
    assert result["fiche_titre"] is None
    assert result["correspondance_faible"] is True


def test_route_diagnostic_exige_authentification(client):
    response = client.post("/api/maintenance/ia/diagnose", json={})
    assert response.status_code == 401


def test_sortie_interactions_restaure_le_json_sans_appel_reseau(monkeypatch):
    app = Flask(__name__)
    app.config.update(GEMINI_API_KEY="cle-factice", GEMINI_MODEL="modele-factice", GEMINI_TIMEOUT=2)
    response_payload = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": '{"ok": true}'}]}]}
    requests = []

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(req, timeout):
        requests.append((req, timeout))
        return FakeResponse(json.dumps(response_payload).encode())

    monkeypatch.setattr(diagnosis.urllib.request, "urlopen", fake_urlopen)
    with app.app_context():
        result = diagnosis._generate_json("Prompt", {"type": "object"})
    request, timeout = requests[0]
    sent = json.loads(request.data)
    assert result == {"ok": True}
    assert timeout == 2
    assert sent["store"] is False
    assert sent["response_format"]["schema"] == {"type": "object"}
    assert request.full_url.endswith("/v1beta/interactions")
