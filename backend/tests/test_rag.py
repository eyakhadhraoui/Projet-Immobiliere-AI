"""Tests de l'assistant documentaire RAG immobilier bilingue (``/api/rag``)."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient


def test_recuperer_checklists_completes(client: FlaskClient) -> None:
    """La route renvoie les deux checklists de location (9 items) et vente (10 items)."""
    reponse = client.get("/api/rag/checklists")
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert "location" in donnees
    assert "vente" in donnees
    assert donnees["location"]["total"] == 9
    assert donnees["vente"]["total"] == 10
    assert len(donnees["location"]["elements"]) == 9
    assert len(donnees["vente"]["elements"]) == 10


def test_recuperer_checklist_filtree(client: FlaskClient) -> None:
    """La route filtre correctement la checklist demandée."""
    reponse = client.get("/api/rag/checklists?transaction=location")
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert "location" in donnees
    assert "vente" not in donnees


def test_recuperer_suggestions_bilingues(client: FlaskClient) -> None:
    """Les questions d'exemple sont disponibles en français et en arabe."""
    rep_fr = client.get("/api/rag/suggestions?langue=fr")
    assert rep_fr.status_code == 200
    donnees_fr = rep_fr.get_json()
    assert len(donnees_fr["suggestions"]) >= 4

    rep_ar = client.get("/api/rag/suggestions?langue=ar")
    assert rep_ar.status_code == 200
    donnees_ar = rep_ar.get_json()
    assert len(donnees_ar["suggestions"]) >= 4


def test_chat_validation_erreur(client: FlaskClient) -> None:
    """Une requête sans message renvoie une erreur 400."""
    reponse = client.post("/api/rag/chat", json={})
    assert reponse.status_code == 400
    donnees = reponse.get_json()
    assert "message" in donnees.get("details", {}) or "message" in donnees


def test_chat_question_location_fr(client: FlaskClient) -> None:
    """Le chatbot répond avec pertinence et cite les textes tunisiens en français."""
    payload = {"message": "Quels sont les documents obligatoires pour louer un appartement en Tunisie ?"}
    reponse = client.post("/api/rag/chat", json=payload)
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["langue"] == "fr"
    assert donnees["transaction"] == "location"
    assert "Code des Obligations et des Contrats" in donnees["reponse"] or "Baladiya" in donnees["reponse"]
    assert len(donnees["sources"]) > 0


def test_chat_question_vente_ar(client: FlaskClient) -> None:
    """Le chatbot répond en arabe avec les sources relatives à la vente et l'Art 377 bis."""
    payload = {"message": "ما هي الوثائق المطلوبة لشراء منزل ومحرر العقد في تونس ؟"}
    reponse = client.post("/api/rag/chat", json=payload)
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["langue"] == "ar"
    assert donnees["transaction"] == "vente"
    assert "377" in donnees["reponse"] or "الرسم العقاري" in donnees["reponse"]


def test_chat_audit_checklist_manquants(client: FlaskClient) -> None:
    """Le système compare les documents déjà réunis et dresse un bilan d'avancement."""
    payload = {
        "message": "Quels documents me manquent pour louer mon appartement ?",
        "transaction": "location",
        "elements_coches": ["cin_proprietaire", "cin_locataire", "contrat_location"],
        "langue": "fr",
    }
    reponse = client.post("/api/rag/chat", json=payload)
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    audit = donnees.get("audit")
    assert audit is not None
    assert audit["total_elements"] == 9
    assert audit["nb_verifies"] == 3
    assert len(audit["presents"]) == 3
    assert len(audit["manquants"]) >= 5
    assert "3 sur 9" in donnees["reponse"]


def test_chat_question_verification_pages_diwan(client: FlaskClient) -> None:
    """Le chatbot répond avec précision sur la vérification des pages et cite Diwan ou le Guide."""
    payload = {"message": "Comment vérifier les pages d'un contrat et que dit la fiche Diwan ?"}
    reponse = client.post("/api/rag/chat", json=payload)
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert len(donnees["sources"]) > 0
    sources_textes = " ".join(s["source"] for s in donnees["sources"])
    assert "Diwan" in sources_textes or "Guide pratique" in sources_textes


def test_analyser_document_texte(client: FlaskClient) -> None:
    """L'endpoint analyse le texte d'un contrat et repère les montants, CINs et complétude."""
    texte = (
        "CONTRAT DE BAIL. Bailleur: M. Ali (CIN 01234567). Preneur: M. Sami (CIN 07654321). "
        "Loyer mensuel: 950 TND. Caution: 1900 TND. Durée: 1 an. "
        "Fait à Tunis le 24/10/2026. Signatures et légalisation Baladiya."
    )
    reponse = client.post("/api/rag/analyser-document", json={"texte": texte, "transaction": "location"})
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["transaction"] == "location"
    assert "01234567" in donnees["champs_extraits"]["cins_trouvees"]
    assert len(donnees["champs_extraits"]["montants_trouves"]) >= 1
    assert donnees["audit_checklist"]["nb_verifies"] >= 3


def test_analyser_document_avec_champs_vides(client: FlaskClient) -> None:
    """L'endpoint détecte les champs à compléter et alerte l'utilisateur."""
    texte = "CONTRAT DE BAIL. Bailleur: M. Foued. Preneur: _________. Loyer: ..... TND."
    reponse = client.post("/api/rag/analyser-document", json={"texte": texte})
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["champs_extraits"]["nb_champs_vides"] > 0
    assert any("champ(s) non renseigné(s)" in a for a in donnees["alertes"])


def test_generer_projet_bail(client: FlaskClient) -> None:
    """L'endpoint génère un contrat de bail tunisien conforme en français et arabe."""
    payload = {
        "type_contrat": "location",
        "langue": "fr",
        "bailleur": {"nom": "Karim Ben Salah", "cin": "01234567", "adresse": "Ennasr", "ville": "Tunis"},
        "locataire": {"nom": "Yassine Mansour", "cin": "08765432", "qualite": "Étudiant"},
        "bien": {"type_bien": "Appartement S+2", "adresse": "Avenue Hédi Nouira", "ville": "Ariana", "surface": 85, "meuble": True},
        "conditions": {"loyer": 850, "caution": 850},
    }
    reponse = client.post("/api/rag/generer-contrat", json=payload)
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert "Karim Ben Salah" in donnees["contrat_markdown"]
    assert "Yassine Mansour" in donnees["contrat_markdown"]
    assert "850" in donnees["contrat_markdown"]
    assert "Baladiya" in donnees["contrat_markdown"]
    assert "60" in donnees["contrat_markdown"]


def test_llm_client_sans_cle(monkeypatch: Any) -> None:
    """Sans clé API configurée, appeler_llm renvoie None sans lever d'exception."""
    from app.ia.rag import llm_client

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "get_client", lambda: None)
    monkeypatch.setattr(llm_client, "ask_ollama", lambda prompt: None)
    rep = llm_client.appeler_llm([{"role": "user", "content": "Test"}])
    assert rep is None


def test_llm_client_mock_succes(monkeypatch: Any) -> None:
    """Vérifie que la réponse du modèle LLM est correctement renvoyée."""
    from unittest.mock import MagicMock
    from app.ia.rag import llm_client

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Réponse générée par Gemini"
    mock_client.models.generate_content.return_value = mock_resp

    monkeypatch.setattr(llm_client, "get_client", lambda: mock_client)
    monkeypatch.setattr(llm_client, "ask_ollama", lambda prompt: None)

    resultat = llm_client.ask_gemini("Question")
    assert resultat == "Réponse générée par Gemini"


def test_assistant_rag_integre_reponse_llm(monkeypatch: Any) -> None:
    """Vérifie qu'AssistantRAG intègre la réponse du LLM quand il est actif."""
    from app.ia.rag.generateur import AssistantRAG

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        "app.ia.rag.generateur.appeler_llm",
        lambda messages: "Explication rédigée par le modèle Gemini pour la Tunisie.",
    )

    assistant = AssistantRAG()
    rep = assistant.repondre("Comment louer un bien ?")
    assert rep["reponse"] == "Explication rédigée par le modèle Gemini pour la Tunisie."


