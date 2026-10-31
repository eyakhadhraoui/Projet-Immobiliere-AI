"""Recherche dans le guide indexé : question -> fiches les plus proches, plus contexte fixe."""
from dataclasses import dataclass
from pathlib import Path

import chromadb
from flask import current_app

from .embeddings import embed_text

COLLECTION = "maintenance_diagnostic_guide"
# Chunks d'introduction : exclus de la recherche, mais toujours fournis comme contexte
CONTEXT_IDS = ("INTRO-URGENCE", "INTRO-SECURITE")


@dataclass
class Hit:
    id: str
    text: str
    metadata: dict
    distance: float  # distance cosinus : plus elle est petite, plus la fiche est proche


class Retriever:
    def __init__(self, db_path: Path, api_key: str):
        self._api_key = api_key
        self._collection = chromadb.PersistentClient(path=str(db_path)).get_collection(COLLECTION)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        vector = embed_text(
            query,
            "RETRIEVAL_QUERY",
            self._api_key,
            timeout=current_app.config.get("GEMINI_TIMEOUT", 120),
        )
        if len(vector) != 3072:
            raise ValueError(f"Dimension d'embedding inattendue : {len(vector)} (3072 attendue).")
        result = self._collection.query(
            query_embeddings=[vector], n_results=k, where={"type": "fiche"}
        )
        return [
            Hit(id=i, text=t, metadata=m, distance=d)
            for i, t, m, d in zip(
                result["ids"][0], result["documents"][0],
                result["metadatas"][0], result["distances"][0],
            )
        ]

    def context(self) -> dict[str, str]:
        """Textes d'introduction (niveaux d'urgence, règles de sécurité), par identifiant."""
        result = self._collection.get(ids=list(CONTEXT_IDS))
        return dict(zip(result["ids"], result["documents"]))
