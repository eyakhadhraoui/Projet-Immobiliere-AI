"""Client LLM unifié avec support Ollama local, Google Gemini (google-genai) et fallback déterministe.

Architecture de résilience :
- appels généraux : Ollama local, puis Google Gemini, puis réponse de repli;
- demandes explicitement privées : Gemini direct sur les seuls extraits sélectionnés par le RAG,
  puis réponse déterministe si Gemini n'est pas disponible.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Chargement du .env
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

try:
    from google import genai
except ImportError:
    genai = None

_client = None

MODELS_FALLBACK = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def get_client() -> Any:
    """Initialise et met en cache le client officiel Google GenAI."""
    global _client
    if _client is None and genai is not None:
        api_key = (
            os.getenv("GEMINI_API_KEY", "").strip()
            or os.getenv("GOOGLE_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        if api_key and not api_key.startswith("votre_") and len(api_key) > 20:
            try:
                _client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.warning(f"[LLM WARNING] Impossible d'initialiser le client Gemini: {e}")
        else:
            _client = None
    return _client


def generer_avec_gemini(prompt: str) -> str | None:
    """Génère directement avec Gemini, sans basculer vers Ollama."""
    client = get_client()
    if not client:
        return None
    model_env = os.getenv("GEMINI_MODEL")
    modeles = ([model_env] if model_env else []) + MODELS_FALLBACK
    for model_name in dict.fromkeys(modeles):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as erreur:
            logger.warning("[LLM DESCRIPTION] Gemini %s indisponible: %s", model_name, str(erreur)[:160])
    return None


def ask_ollama(prompt: str) -> str | None:
    """Appelle le modèle LLM local Ollama si le service est actif sur le port 11434.

    Args:
        prompt: Texte de la consigne ou question.

    Returns:
        str | None: Réponse générée ou None si Ollama est injoignable.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    parsed_url = urlparse(base_url)
    host = parsed_url.hostname or "127.0.0.1"
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 11434)
    try:
        with socket.create_connection((host, port), timeout=0.2):
            pass
    except Exception:
        return None

    url = f"{base_url}/api/generate"
    model_configure = os.getenv("OLLAMA_RAG_MODEL", "").strip()
    models_to_try = (
        [model_configure] if model_configure else []
    ) + ["llama3.2:1b", "llama3.2", "mistral", "llama3"]
    timeout = float(os.getenv("OLLAMA_RAG_TIMEOUT", "60"))

    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                res_text = res_json.get("response", "").strip()
                if res_text:
                    logger.info(f"[LLM OLLAMA SUCCESS] Réponse générée avec le modèle local Ollama: {model_name}")
                    return res_text
        except Exception:
            continue
    return None


def ask_gemini(prompt: str, fallback_default: str | None = None) -> str:
    """Orchestre la génération avec priorité Ollama local, puis cascade Gemini, puis fallback.

    Args:
        prompt: Texte à envoyer au modèle.
        fallback_default: Texte de repli déterministe si aucune API ne répond.

    Returns:
        str: Réponse textuelle finale.
    """
    # 1. Priorité au LLM local Ollama (100% gratuit, local, sans quota)
    ollama_res = ask_ollama(prompt)
    if ollama_res:
        return ollama_res

    # 2. Secours Gemini API (si Ollama indisponible)
    client = get_client()
    if client:
        # Prendre en compte le modèle configuré en premier s'il est spécifié
        model_env = os.getenv("OPENAI_MODEL") or os.getenv("GEMINI_MODEL")
        modeles_cibles = list(MODELS_FALLBACK)
        if model_env and model_env not in modeles_cibles:
            modeles_cibles.insert(0, model_env)

        for model_name in modeles_cibles:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                err_str = str(e)
                logger.warning(f"[LLM WARNING] Modèle Gemini {model_name} indisponible : {err_str[:120]}")
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str or "404" in err_str or "503" in err_str:
                    continue

    logger.warning("[LLM WARNING] Quota LLM épuisé ou indisponible. Utilisation du fallback déterministe.")
    if fallback_default is not None:
        return fallback_default
    return '{"event_type": "contrat", "justification": "Évaluation basée sur les règles métier et les garanties contractuelles.", "anomalies": []}'


def appeler_llm(
    messages: list[dict[str, str]],
    model_override: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    timeout_secondes: int = 20,
    local_uniquement: bool = False,
    gemini_uniquement: bool = False,
) -> str | None:
    """Interface unifiée pour AssistantRAG convertissant les messages en appel LLM.

    Args:
        messages: Liste des messages [{"role": "system"|"user", "content": "..."}].
        model_override: Modèle spécifique optionnel.
        temperature: Paramètre créativité.
        max_tokens: Jetons maximum.
        timeout_secondes: Délai maximal d'attente.
        local_uniquement: N'utilise qu'Ollama, sans envoyer le contenu à un service externe.
        gemini_uniquement: Appelle Gemini directement, sans essayer Ollama en premier.

    Returns:
        str | None: Réponse générée ou None.
    """
    # Assembler le prompt complet pour ask_gemini
    parties: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        contenu = m.get("content", "")
        if role == "system":
            parties.append(f"Instructions système :\n{contenu}\n")
        elif role == "user":
            parties.append(f"Utilisateur :\n{contenu}\n")
        else:
            parties.append(f"{role} :\n{contenu}\n")

    prompt_complet = "\n".join(parties).strip()
    if gemini_uniquement:
        resultat_gemini = generer_avec_gemini(prompt_complet)
        return resultat_gemini.strip() if resultat_gemini and resultat_gemini.strip() else None
    if local_uniquement:
        resultat_local = ask_ollama(prompt_complet)
        return resultat_local.strip() if resultat_local and resultat_local.strip() else None

    resultat = ask_gemini(prompt_complet, fallback_default="")
    return resultat.strip() if resultat and resultat.strip() else None
