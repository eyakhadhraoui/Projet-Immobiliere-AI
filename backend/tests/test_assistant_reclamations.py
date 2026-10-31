"""Tests de l'intégration Gemini de l'assistant des réclamations."""

from __future__ import annotations

from io import BytesIO
import json
import urllib.error
from unittest.mock import patch

import pytest

from app.services.assistant_reclamations import (
    AssistantReclamationError,
    DESCRIPTION_SCHEMA,
    GeminiReclamationError,
    SCHEMA,
    ameliorer_description_reclamation,
    analyser_avec_gemini,
)


SUGGESTION = {
    "motif_suggere": "fausse_annonce",
    "priorite_suggeree": "haute",
    "raison_priorite": "Une avance est évoquée avant la visite.",
    "pieces_a_fournir": ["Capture du message"],
    "conseil": "Vérifier les échanges transmis.",
    "brouillon_reponse": "Bonjour, votre signalement a bien été reçu.",
}


@pytest.fixture(autouse=True)
def _gemini_fournisseur_par_defaut(app):
    """Les tests Gemini choisissent explicitement ce fournisseur, sans dépendre de l'environnement."""
    app.config["RECLAMATIONS_LLM_PROVIDER"] = "gemini"


class FauxReponse(BytesIO):
    """Réponse HTTP JSON compatible avec le contexte de gestion."""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _reponse_gemini(donnees: dict) -> FauxReponse:
    texte = json.dumps(donnees, ensure_ascii=False)
    return FauxReponse(json.dumps({
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": texte}]}],
    }).encode("utf-8"))


def _reponse_ollama(donnees: dict) -> FauxReponse:
    return FauxReponse(json.dumps({
        "message": {"role": "assistant", "content": json.dumps(donnees, ensure_ascii=False)},
        "done": True,
    }).encode("utf-8"))


def test_ollama_local_analyse_en_json_sans_cle_externe(app) -> None:
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        return_value=_reponse_ollama(SUGGESTION),
    ) as appel:
        app.config["RECLAMATIONS_LLM_PROVIDER"] = "ollama"
        app.config["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"
        app.config["OLLAMA_RECLAMATION_MODEL"] = "qwen2.5:3b"
        resultat = analyser_avec_gemini("Objet local", "Description privee")

    requete = appel.call_args.args[0]
    corps = json.loads(requete.data.decode("utf-8"))
    assert requete.full_url == "http://127.0.0.1:11434/api/chat"
    assert corps["model"] == "qwen2.5:3b"
    assert corps["stream"] is False
    assert corps["format"] == SCHEMA
    assert "Description privee" in corps["messages"][1]["content"]
    assert not any(key.lower() == "x-goog-api-key" for key in requete.headers)
    assert resultat["mention"].startswith("Analyse Ollama")


def test_ollama_absent_ou_modele_manquant_est_signale_sans_fallback_externe(app) -> None:
    erreur_http = urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", 404, "Not Found", hdrs=None, fp=BytesIO())
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen", side_effect=erreur_http
    ):
        app.config["RECLAMATIONS_LLM_PROVIDER"] = "ollama"
        with pytest.raises(AssistantReclamationError, match="n'est pas installé") as erreur:
            analyser_avec_gemini("Objet", "Description")
    assert erreur.value.status == 503


def test_analyser_appelle_gemini_sans_stockage_et_valide_sortie(app) -> None:
    """Envoie les seuls champs de texte à Gemini et borne la réponse structurée."""
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        return_value=_reponse_gemini(SUGGESTION),
    ) as appel:
        app.config["GEMINI_API_KEY"] = "cle-de-test-uniquement"
        resultat = analyser_avec_gemini("Prix inhabituellement bas", "Demande d'avance avant visite.")

    requete = appel.call_args.args[0]
    corps = json.loads(requete.data.decode("utf-8"))
    assert "Prix inhabituellement bas" in corps["input"]
    assert corps["model"] == app.config["GEMINI_MODEL"]
    assert corps["response_format"] == [{
        "type": "text",
        "mime_type": "application/json",
        "schema": SCHEMA,
    }]
    assert corps["generation_config"] == {"thinking_level": "low"}
    assert corps["store"] is False
    assert resultat["motif_suggere"] == "fausse_annonce"
    assert resultat["priorite_suggeree"] == "haute"
    assert resultat["mention"].startswith("Analyse Gemini")


def test_gemini_est_le_fournisseur_par_defaut() -> None:
    """Une configuration sans fournisseur choisit Gemini par defaut."""
    from app.config import Config

    assert Config.RECLAMATIONS_LLM_PROVIDER == "gemini"


def test_gemini_absent_est_signale(app) -> None:
    """Ne remplace pas silencieusement Gemini par une suggestion locale."""
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""
        client = app.test_client()
        reponse = client.post(
            "/api/reclamations/assistant/analyser",
            json={"objet": "Objet", "description": "Description"},
        )

    assert reponse.status_code == 503
    assert reponse.get_json()["error"] == "assistant_reclamation_indisponible"


def test_503_gemini_reessaie_une_fois_en_conservant_la_meme_cle(app) -> None:
    """Une surcharge temporaire déclenche un seul nouvel essai avec la configuration inchangée."""
    erreur = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        503,
        "Unavailable",
        hdrs=None,
        fp=BytesIO(b'{"error":{"code":"service_unavailable"}}'),
    )
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[erreur, _reponse_gemini(SUGGESTION)],
    ) as appel, patch("app.services.assistant_reclamations.time.sleep") as attente:
        app.config["GEMINI_API_KEY"] = "meme-cle-de-test"
        resultat = analyser_avec_gemini("Objet de test", "Description fictive.")

    assert resultat["motif_suggere"] == "fausse_annonce"
    assert appel.call_count == 2
    assert attente.call_args.args == (1,)
    for appel_simule in appel.call_args_list:
        requete = appel_simule.args[0]
        assert {nom.lower(): valeur for nom, valeur in requete.headers.items()}["x-goog-api-key"] == "meme-cle-de-test"


def test_503_gemini_apres_nouvel_essai_est_explicite(app) -> None:
    """Un service toujours indisponible est signale sans faux resultat."""
    erreur1 = urllib.error.HTTPError("https://example.test", 503, "Unavailable", hdrs=None, fp=BytesIO())
    erreur2 = urllib.error.HTTPError("https://example.test", 503, "Unavailable", hdrs=None, fp=BytesIO())
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[erreur1, erreur2],
    ), patch("app.services.assistant_reclamations.time.sleep"):
        app.config["GEMINI_API_KEY"] = "meme-cle-de-test"
        app.config["GEMINI_RECLAMATION_FALLBACK_MODEL"] = ""
        with pytest.raises(GeminiReclamationError, match="Gemini est temporairement indisponible") as erreur:
            analyser_avec_gemini("Objet de test", "Description fictive.")

    assert erreur.value.status == 503
    assert "meme-cle-de-test" not in erreur.value.message


def test_503_gemini_passe_au_modele_de_repli(app) -> None:
    erreurs = [
        urllib.error.HTTPError("https://example.test", 503, "Unavailable", hdrs=None, fp=BytesIO())
        for _ in range(2)
    ]
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[*erreurs, _reponse_gemini(SUGGESTION)],
    ) as appel, patch("app.services.assistant_reclamations.time.sleep"):
        app.config["GEMINI_API_KEY"] = "cle-de-test"
        app.config["GEMINI_RECLAMATION_MODEL"] = "gemini-3.8-flash"
        app.config["GEMINI_RECLAMATION_FALLBACK_MODEL"] = "gemini-3.7-flash"
        resultat = analyser_avec_gemini("Objet de test", "Description fictive.")

    modeles = [json.loads(invocation.args[0].data.decode("utf-8"))["model"] for invocation in appel.call_args_list]
    assert modeles == ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.7-flash"]
    assert resultat["motif_suggere"] == "fausse_annonce"


def test_429_gemini_bascule_directement_vers_le_modele_de_repli(app) -> None:
    """Une limite par modèle déclenche le secours sans répéter l'appel limité."""
    limite = urllib.error.HTTPError(
        "https://example.test", 429, "Too Many Requests", hdrs=None, fp=BytesIO()
    )
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[limite, _reponse_gemini(SUGGESTION)],
    ) as appel, patch("app.services.assistant_reclamations.time.sleep") as attente:
        app.config["GEMINI_API_KEY"] = "cle-de-test"
        app.config["GEMINI_RECLAMATION_MODEL"] = "gemini-3.8-flash"
        app.config["GEMINI_RECLAMATION_FALLBACK_MODEL"] = "gemini-3.6-flash"
        resultat = analyser_avec_gemini("Objet fictif", "Description fictive.")

    modeles = [
        json.loads(invocation.args[0].data.decode("utf-8"))["model"]
        for invocation in appel.call_args_list
    ]
    assert modeles == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert resultat["motif_suggere"] == "fausse_annonce"
    attente.assert_not_called()


def test_429_gemini_sur_modele_de_repli_affiche_limite_et_statut(app) -> None:
    """Si Google limite aussi le secours, l'API renvoie une erreur explicite sans secret."""
    erreurs = [
        urllib.error.HTTPError(
            "https://example.test", 429, "Too Many Requests", hdrs=None, fp=BytesIO()
        )
        for _ in range(2)
    ]
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=erreurs,
    ) as appel:
        app.config["GEMINI_API_KEY"] = "cle-secrete-de-test"
        app.config["GEMINI_RECLAMATION_MODEL"] = "gemini-3.8-flash"
        app.config["GEMINI_RECLAMATION_FALLBACK_MODEL"] = "gemini-3.6-flash"
        with pytest.raises(GeminiReclamationError, match="quotas du projet") as erreur:
            analyser_avec_gemini("Objet fictif", "Description fictive.")

    modeles = [
        json.loads(invocation.args[0].data.decode("utf-8"))["model"]
        for invocation in appel.call_args_list
    ]
    assert modeles == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert erreur.value.status == 429
    assert "cle-secrete-de-test" not in erreur.value.message


def test_timeout_gemini_bascule_vers_le_modele_de_repli_en_gardant_la_cle(app) -> None:
    """Un timeout du modele principal declenche le modele de repli avec la meme cle."""
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[TimeoutError("delai simule"), _reponse_gemini(SUGGESTION)],
    ) as appel, patch("app.services.assistant_reclamations.time.sleep") as attente:
        app.config["GEMINI_API_KEY"] = "cle-conservee-test"
        app.config["GEMINI_RECLAMATION_MODEL"] = "gemini-3.8-flash"
        app.config["GEMINI_RECLAMATION_FALLBACK_MODEL"] = "gemini-3.6-flash"
        resultat = analyser_avec_gemini("Objet", "Description")

    assert resultat["motif_suggere"] == "fausse_annonce"
    assert appel.call_count == 2
    attente.assert_not_called()
    requetes = [invocation.args[0] for invocation in appel.call_args_list]
    modeles = [json.loads(requete.data.decode("utf-8"))["model"] for requete in requetes]
    assert modeles == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert all(requete.headers["X-goog-api-key"] == "cle-conservee-test" for requete in requetes)


def test_timeout_gemini_restant_retourne_504_explicite(app) -> None:
    """Si les deux appels expirent, aucune suggestion n'est fabriquée."""
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        side_effect=[TimeoutError("premier"), TimeoutError("second")],
    ), patch("app.services.assistant_reclamations.time.sleep"):
        app.config["GEMINI_API_KEY"] = "cle-conservee-test"
        with pytest.raises(GeminiReclamationError, match="attente") as erreur:
            analyser_avec_gemini("Objet", "Description")

    assert erreur.value.status == 504
    assert "cle-conservee-test" not in erreur.value.message


def test_endpoint_gemini_garde_les_decisions_manuellement(app, monkeypatch) -> None:
    """L'API renvoie la suggestion Gemini sans suspendre ni modifier une annonce."""
    monkeypatch.setattr(
        "app.routes.reclamations.analyser_avec_gemini",
        lambda _objet, _description: {
            **SUGGESTION,
            "mention": "Analyse Gemini indicative. Le modérateur reste seul décisionnaire.",
        },
    )
    with app.app_context():
        reponse = app.test_client().post(
            "/api/reclamations/assistant/analyser",
            json={"objet": "Objet", "description": "Description"},
        )

    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["motif_suggere"] == "fausse_annonce"
    assert donnees["brouillon_reponse"]
    assert donnees["doublon_possible"] is False


def test_amelioration_description_appelle_gemini_et_borne_la_proposition(app) -> None:
    """Gemini reçoit les seuls textes fournis et renvoie une proposition distincte."""
    proposition = "Je signale une différence entre le prix affiché et le prix communiqué."
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen",
        return_value=_reponse_gemini({"description": proposition}),
    ) as appel:
        app.config["GEMINI_API_KEY"] = "cle-de-test-uniquement"
        resultat = ameliorer_description_reclamation("Prix incohérent", "Le propriétaire m'a communiqué un autre prix.")

    corps = json.loads(appel.call_args.args[0].data.decode("utf-8"))
    assert corps["response_format"][0]["schema"] == DESCRIPTION_SCHEMA
    assert "Prix incohérent" in corps["input"]
    assert "Le propriétaire m'a communiqué un autre prix." in corps["input"]
    assert corps["store"] is False
    assert resultat == proposition


def test_amelioration_description_exige_un_objet_ou_des_faits(app) -> None:
    with app.app_context(), patch(
        "app.services.assistant_reclamations.urllib.request.urlopen"
    ) as appel:
        with pytest.raises(AssistantReclamationError, match="Saisissez un objet") as erreur:
            ameliorer_description_reclamation(" ", " ")

    assert erreur.value.status == 400
    appel.assert_not_called()


def test_endpoint_amelioration_renvoie_une_proposition_sans_decider(app, monkeypatch) -> None:
    proposition = "Je souhaite signaler une différence de prix."
    monkeypatch.setattr(
        "app.routes.reclamations.ameliorer_description_reclamation",
        lambda objet, description: proposition,
    )
    with app.app_context():
        reponse = app.test_client().post(
            "/api/reclamations/assistant/ameliorer-description",
            json={"objet": "Prix différent", "description": "Le tarif communiqué n'est pas celui affiché."},
        )

    assert reponse.status_code == 200
    assert reponse.get_json()["description"] == proposition
    assert "relisez" in reponse.get_json()["mention"]


def test_endpoint_amelioration_refuse_un_texte_vide(app) -> None:
    with app.app_context():
        reponse = app.test_client().post(
            "/api/reclamations/assistant/ameliorer-description",
            json={"objet": " ", "description": " "},
        )

    assert reponse.status_code == 400
    assert reponse.get_json()["error"] == "validation"
