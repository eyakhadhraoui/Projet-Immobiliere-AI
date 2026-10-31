"""Ingestion et recherche vectorielle des PDF RAG."""

from __future__ import annotations

import io
import logging
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from app.ia.rag.analyseur_document import decouper_en_chunks
from app.ia.rag.corpus import obtenir_corpus

RAG_DIR = Path(__file__).resolve().parents[3] / "instance" / "rag"
VECTOR_DIR = RAG_DIR / "chroma"
UPLOAD_DIR = RAG_DIR / "uploads"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEED_PDF = Path(__file__).with_name("documents") / "guide_documents_location_vente_tunisie.pdf"
SEED_ID = "guide-location-vente-tunisie"
logger = logging.getLogger(__name__)


class DocumentRAGError(ValueError):
    """Erreur de validation ou d'ingestion d'un PDF."""


@lru_cache(maxsize=1)
def _modele():
    """Charge Sentence Transformers hors ligne, sinon un encodeur local de secours."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=True)
    except Exception as erreur:
        logger.warning(
            "Modele multilingue indisponible localement (%s); embeddings caracteres de secours actifs.",
            erreur,
        )

    from sklearn.feature_extraction.text import HashingVectorizer

    class EncodeurHachage:
        backend = "hachage-caracteres-v1"

        def __init__(self):
            self.vectoriseur = HashingVectorizer(
                analyzer="char",
                ngram_range=(2, 5),
                n_features=384,
                alternate_sign=False,
                norm="l2",
                lowercase=True,
            )

        def encode(self, textes, **_options):
            return self.vectoriseur.transform(textes).toarray()

    return EncodeurHachage()


@lru_cache(maxsize=1)
def _collection():
    import chromadb

    modele = _modele()
    backend = getattr(modele, "backend", "sentence-transformers")
    nom_collection = "documents_immobiliers" if backend == "sentence-transformers" else "documents_immobiliers_hachage"
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DIR))
    return client.get_or_create_collection(
        name=nom_collection,
        metadata={"hnsw:space": "cosine", "embedding_model": MODEL_NAME if backend == "sentence-transformers" else backend},
    )


def _extraire_pages(contenu: bytes) -> list[dict[str, Any]]:
    if not contenu.startswith(b"%PDF-"):
        raise DocumentRAGError("Le fichier fourni n'est pas un PDF valide.")
    try:
        import fitz

        document = fitz.open(stream=contenu, filetype="pdf")
    except ImportError as erreur:
        raise RuntimeError("Installez PyMuPDF avec `python -m pip install -r requirements.txt`.") from erreur
    except Exception as erreur:
        raise DocumentRAGError("Le PDF est illisible ou protégé par mot de passe.") from erreur
    if len(document) > 150:
        raise DocumentRAGError("Le PDF dépasse la limite de 150 pages.")

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        pytesseract = None
        Image = None

    pages: list[dict[str, Any]] = []
    try:
        langues_installees = set(pytesseract.get_languages(config="")) if pytesseract else set()
    except Exception:
        langues_installees = set()
    langues = "+".join(langue for langue in ("fra", "ara", "eng") if langue in langues_installees) or "eng"
    for numero, page in enumerate(document, start=1):
        texte = (page.get_text("text") or "").strip()
        ocr = False
        if len(texte) < 30 and pytesseract and Image:
            try:
                image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_pil = Image.open(io.BytesIO(image.tobytes("png")))
                texte_ocr = pytesseract.image_to_string(image_pil, lang=langues).strip()
                if len(texte_ocr) > len(texte):
                    texte, ocr = texte_ocr, True
            except Exception:
                # L'extraction native reste utile pour les pages non scannées.
                pass
        pages.append({"numero_physique": numero, "texte": texte, "ocr": ocr})
    document.close()
    if not any(page["texte"] for page in pages):
        raise DocumentRAGError(
            "Aucun texte lisible n'a été trouvé. Pour un PDF scanné, installez Tesseract et ses données linguistiques françaises/arabes."
        )
    return pages


def _indexer_pdf(
    *,
    contenu: bytes,
    document_id: str,
    nom: str,
    user_id: str,
    document_type: str = "uploaded",
    source: str | None = None,
) -> dict[str, Any]:
    pages = _extraire_pages(contenu)
    chunks = decouper_en_chunks(pages, taille_chunk=1000, chevauchement=140)
    if not chunks:
        raise DocumentRAGError("Le PDF ne contient pas de texte indexable.")

    textes = [chunk["texte"] for chunk in chunks]
    vecteurs = _modele().encode(textes, normalize_embeddings=True, show_progress_bar=False).tolist()
    collection = _collection()
    collection.add(
        ids=[f"{document_id}:{chunk['index']}" for chunk in chunks],
        embeddings=vecteurs,
        documents=textes,
        metadatas=[
            {
                "document_id": document_id,
                "user_id": user_id,
                "nom": nom,
                "source": source or nom,
                "type": document_type,
                "page": int(chunk["page"]),
                "chunk": int(chunk["index"]),
                "ocr": bool(pages[int(chunk["page"]) - 1].get("ocr", False)),
            }
            for chunk in chunks
        ],
    )
    return {"id": document_id, "nom": nom, "pages": len(pages), "passages": len(chunks)}


def initialiser_base_publique() -> None:
    """Ajoute le corpus légal et le PDF de référence au premier démarrage."""
    collection = _collection()
    for document in obtenir_corpus():
        identifiant = f"reference-{document['id']}"
        if collection.get(where={"document_id": identifiant}, limit=1)["ids"]:
            continue
        pages = [{"numero_physique": 1, "texte": f"{document['titre_fr']}\n{document['contenu_fr']}\n{document['titre_ar']}\n{document['contenu_ar']}"}]
        chunks = decouper_en_chunks(pages, taille_chunk=1000, chevauchement=140)
        textes = [chunk["texte"] for chunk in chunks]
        vecteurs = _modele().encode(textes, normalize_embeddings=True, show_progress_bar=False).tolist()
        collection.add(
            ids=[f"{identifiant}:{chunk['index']}" for chunk in chunks],
            embeddings=vecteurs,
            documents=textes,
            metadatas=[{
                "document_id": identifiant,
                "user_id": "public",
                "nom": document["titre_fr"],
                "source": document["source"],
                "type": "reference",
                "theme": document.get("theme", "general"),
                "page": 0,
                "chunk": int(chunk["index"]),
                "ocr": False,
            } for chunk in chunks],
        )

    if not collection.get(where={"document_id": SEED_ID}, limit=1)["ids"] and SEED_PDF.exists():
        _indexer_pdf(
            contenu=SEED_PDF.read_bytes(),
            document_id=SEED_ID,
            nom=SEED_PDF.name,
            user_id="public",
            document_type="guide",
            source="Guide documentaire fourni — pages du PDF",
        )


def ajouter_pdf(contenu: bytes, nom_original: str, user_id: str) -> dict[str, Any]:
    """Conserve le PDF et indexe ses passages dans la base Chroma persistante.

    Le fichier est écrit avant l'indexation. Si l'indexation échoue, le fichier et tout éventuel index
    partiel sont supprimés pour éviter de laisser un document qui semble importé mais ne peut pas être recherché.
    """
    nom = secure_filename(nom_original or "document.pdf")
    if not nom.lower().endswith(".pdf"):
        raise DocumentRAGError("Seuls les fichiers PDF sont acceptés.")
    if not contenu:
        raise DocumentRAGError("Le fichier PDF est vide.")
    document_id = uuid.uuid4().hex
    dossier = UPLOAD_DIR / str(user_id)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{document_id}.pdf"
    try:
        chemin.write_bytes(contenu)
        return _indexer_pdf(contenu=contenu, document_id=document_id, nom=nom, user_id=str(user_id))
    except Exception:
        try:
            _collection().delete(where={"document_id": document_id})
        except Exception:
            logger.exception("Nettoyage de l'index incomplet impossible pour le document %s", document_id)
        chemin.unlink(missing_ok=True)
        raise


def lister_documents(user_id: str | None) -> list[dict[str, Any]]:
    initialiser_base_publique()
    collection = _collection()
    resultats = collection.get(include=["metadatas"], limit=10000)
    documents: dict[str, dict[str, Any]] = {}
    for metadata in resultats.get("metadatas") or []:
        if not metadata:
            continue
        proprietaire = str(metadata.get("user_id", "public"))
        if proprietaire not in ("public", str(user_id)):
            continue
        identifiant = metadata["document_id"]
        entree = documents.setdefault(identifiant, {
            "id": identifiant,
            "nom": metadata["nom"],
            "source": metadata["source"],
            "type": metadata["type"],
            "pages": set(),
            "passages": 0,
            "ocr": False,
            "supprimable": proprietaire != "public",
        })
        entree["passages"] += 1
        if metadata.get("page", 0) > 0:
            entree["pages"].add(metadata["page"])
        entree["ocr"] = entree["ocr"] or metadata.get("ocr", False)
    return [
        {**doc, "pages": len(doc["pages"])}
        for doc in sorted(documents.values(), key=lambda item: item["nom"].lower())
    ]


def suggestions_pdf(user_id: str | None, langue: str = "fr", transaction: str = "general") -> list[dict[str, str]]:
    """Construit des questions suggérées à partir des titres et intertitres des PDF du compte.

    Les questions sont extraites localement des métadonnées et des passages indexés; aucun contenu privé
    n'est envoyé à un service externe. Les documents publics ne produisent pas de suggestions personnalisées.
    """
    if not user_id:
        return []

    collection = _collection()
    resultats = collection.get(
        where={"user_id": str(user_id)},
        include=["documents", "metadatas"],
        limit=10000,
    )
    textes = resultats.get("documents") or []
    metadonnees = resultats.get("metadatas") or []
    par_document: dict[str, dict[str, Any]] = {}
    for texte, metadata in zip(textes, metadonnees):
        if not metadata or metadata.get("type") != "uploaded":
            continue
        document_id = str(metadata.get("document_id", ""))
        if not document_id:
            continue
        document = par_document.setdefault(document_id, {
            "nom": metadata.get("nom", "PDF importé"),
            "passages": [],
        })
        document["passages"].append((int(metadata.get("page", 0)), int(metadata.get("chunk", 0)), texte or ""))

    suggestions: list[dict[str, str]] = []
    ponctuation = ".!?؟؛:;"
    for document_id, document in par_document.items():
        nom = Path(str(document["nom"])).stem.replace("_", " ").replace("-", " ").strip()
        nom = nom or "ce PDF"
        intertitres: list[str] = []
        vus: set[str] = set()
        for _page, _chunk, texte in sorted(document["passages"]):
            for ligne in texte.splitlines():
                titre = re.sub(r"^\s*(?:(?:\d+(?:\.\d+)*|[IVXLCDM]+)[.)-]?\s+|[-*•]\s+)", "", ligne).strip()
                titre = " ".join(titre.split())
                mots = titre.split()
                cle = titre.casefold()
                if not 2 <= len(mots) <= 9 or not 8 <= len(titre) <= 90 or titre[-1:] in ponctuation:
                    continue
                if cle in vus or titre.lower().startswith(("page ", "table des matières", "sommaire")):
                    continue
                vus.add(cle)
                intertitres.append(titre.strip(" -–—•"))
                if len(intertitres) >= 3:
                    break
            if len(intertitres) >= 3:
                break

        themes = intertitres or [""]
        for indice, theme in enumerate(themes):
            if langue == "ar":
                question = (
                    f"ماذا يذكر ملف «{nom}» بخصوص «{theme}»؟" if theme
                    else f"ما أهم المعلومات الواردة في ملف «{nom}»؟"
                )
                titre_suggestion = f"عن {theme}" if theme else f"ملخص {nom}"
            else:
                question = (
                    f"Que précise le PDF « {nom} » au sujet de « {theme} » ?" if theme
                    else f"Quels sont les points importants du PDF « {nom} » ?"
                )
                titre_suggestion = theme[:48] if theme else f"Résumé : {nom[:38]}"
            suggestions.append({
                "id": f"pdf-{document_id}-{indice}",
                "titre": titre_suggestion,
                "question": question,
                "transaction": transaction if transaction in ("location", "vente") else "general",
                "source": "pdf",
            })
            if len(suggestions) >= 6:
                return suggestions
    return suggestions


def supprimer_pdf(document_id: str, user_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{32}", document_id):
        return False
    collection = _collection()
    entree = collection.get(where={"document_id": document_id}, include=["metadatas"], limit=1)
    metadatas = entree.get("metadatas") or []
    if not metadatas or str(metadatas[0].get("user_id")) != str(user_id):
        return False
    collection.delete(where={"document_id": document_id})
    chemin = UPLOAD_DIR / str(user_id) / f"{document_id}.pdf"
    chemin.unlink(missing_ok=True)
    return True


def chercher_pdf(
    requete: str,
    user_id: str | None,
    top_k: int = 5,
    page: int | None = None,
) -> list[dict[str, Any]]:
    """Recherche les passages PDF; ``page`` permet de cibler une page précise des PDF privés."""
    initialiser_base_publique()
    collection = _collection()
    vecteur = _modele().encode([requete], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
    scopes = ["public"]
    if user_id is not None:
        scopes.append(str(user_id))
    extraits: list[dict[str, Any]] = []
    for scope in scopes:
        filtre: dict[str, Any] = {"user_id": scope}
        if page is not None:
            filtre = {"$and": [
                {"user_id": scope},
                {"page": page},
                {"type": "uploaded"},
            ]}
        resultat = collection.query(
            query_embeddings=[vecteur],
            n_results=top_k,
            where=filtre,
            include=["documents", "metadatas", "distances"],
        )
        ids = (resultat.get("ids") or [[]])[0]
        textes = (resultat.get("documents") or [[]])[0]
        metadatas = (resultat.get("metadatas") or [[]])[0]
        distances = (resultat.get("distances") or [[]])[0]
        for identifiant, texte, metadata, distance in zip(ids, textes, metadatas, distances):
            score = round(1 - float(distance), 4)
            if page is None and score < 0.18:
                continue
            page = metadata.get("page", 0)
            source = metadata["source"] + (f" — page {page}" if page else "")
            extraits.append({
                "id": identifiant,
                "titre": metadata["nom"],
                "source": source,
                "contenu": texte,
                "theme": metadata.get("theme", "document"),
                "score": score,
                "page": page or None,
                "type": metadata.get("type", "document"),
                "prive": str(metadata.get("user_id", "public")) != "public",
            })
    extraits.sort(key=lambda item: item["score"], reverse=True)
    uniques: dict[str, dict[str, Any]] = {}
    for extrait in extraits:
        uniques.setdefault(extrait["id"], extrait)
    return list(uniques.values())[:top_k]
