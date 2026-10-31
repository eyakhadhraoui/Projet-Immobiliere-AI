"""Calcul d'embeddings avec l'API Gemini (REST) : texte en entrée, vecteur en sortie."""
import json
import time
import urllib.error
import urllib.request

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
DEFAULT_MODEL = "gemini-embedding-001"
# Quota (429) et erreurs serveur de Google : on réessaie avec une pause croissante
RETRYABLE_STATUS = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 3


class EmbeddingError(Exception):
    """Échec du calcul d'un embedding."""


def embed_text(text: str, task_type: str, api_key: str,
               model: str = DEFAULT_MODEL, timeout: int = 30) -> list[float]:
    """task_type : RETRIEVAL_DOCUMENT pour indexer une fiche, RETRIEVAL_QUERY pour une question."""
    body = {
        "model": f"models/{model}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
    }
    request = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)["embedding"]["values"]
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")[:300]
            if err.code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                time.sleep(5 * attempt)
                continue
            raise EmbeddingError(f"HTTP {err.code} : {detail}") from err
        except (TimeoutError, urllib.error.URLError) as err:
            raise EmbeddingError(f"Service d'embeddings injoignable : {err}") from err
        except (KeyError, json.JSONDecodeError) as err:
            raise EmbeddingError("Réponse inattendue du service d'embeddings.") from err
    raise EmbeddingError("Échec après plusieurs essais.")  # inatteignable, par sécurité