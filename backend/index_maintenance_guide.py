"""Construit l'index Chroma dédié au guide de diagnostic maintenance (25 vecteurs Gemini)."""

from pathlib import Path

import chromadb

from app.config import Config
from app.ia.maintenance_rag.chunker import build_chunks
from app.ia.maintenance_rag.embeddings import DEFAULT_MODEL, embed_text
from app.ia.maintenance_rag.retriever import COLLECTION

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "app" / "ia" / "maintenance_rag" / "data"
PDF_PATH = DATA_DIR / "guide.pdf"
DB_PATH = BACKEND_DIR / "maintenance_rag_chroma"
EXPECTED_CHUNKS = 25
EXPECTED_DIMENSIONS = 3072


def main() -> None:
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        raise SystemExit("GEMINI_API_KEY absent : renseignez-la dans backend/.env avant l'indexation.")
    chunks = build_chunks(str(PDF_PATH))
    if len(chunks) != EXPECTED_CHUNKS:
        raise SystemExit(f"Le guide doit produire {EXPECTED_CHUNKS} chunks, {len(chunks)} trouvés.")

    vectors = []
    for index, chunk in enumerate(chunks, start=1):
        vector = embed_text(
            chunk.text,
            "RETRIEVAL_DOCUMENT",
            api_key,
            model=DEFAULT_MODEL,
            timeout=Config.GEMINI_TIMEOUT,
        )
        if len(vector) != EXPECTED_DIMENSIONS:
            raise SystemExit(f"Dimension invalide pour {chunk.id}: {len(vector)} au lieu de {EXPECTED_DIMENSIONS}.")
        vectors.append(vector)
        print(f"[{index}/{len(chunks)}] {chunk.id} indexé en mémoire.")

    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    collection.upsert(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=vectors,
        metadatas=[chunk.metadata for chunk in chunks],
    )
    print(f"Index maintenance prêt : {collection.count()} éléments, collection {COLLECTION}, modèle {DEFAULT_MODEL}.")


if __name__ == "__main__":
    main()
