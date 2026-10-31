"""Services de réponse factuelle aux questions d'un dossier litigieux."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app import db
from app.ia.litiges.analyse import repondre
from app.models import CitationLitige, DossierLitige, PassageLitige, QuestionLitige


def repondre_question(
    dossier: DossierLitige, question: str, chemin_modele: str | None = None
) -> dict[str, Any]:
    """Analyse une question uniquement à partir des passages du dossier fourni.

    Args:
        dossier: Dossier déjà autorisé pour l'utilisateur courant.
        question: Question factuelle validée par le schéma de l'API.
        chemin_modele: Chemin facultatif vers un modèle sémantique local.

    Returns:
        dict[str, Any]: Réponse prudente, citations et résultats de recherche.
    """
    passages = db.session.scalars(
        select(PassageLitige)
        .where(PassageLitige.case_id == dossier.case_id)
        .order_by(PassageLitige.id)
    ).all()
    documents = {document.id: document for document in dossier.documents}
    sources = [
        {
            "chunk_id": passage.chunk_id,
            "document_id": passage.document_id,
            "nom_fichier": documents[passage.document_id].nom_fichier if passage.document_id in documents else "Document",
            "titre": documents[passage.document_id].titre if passage.document_id in documents else "Document",
            "role_auteur": documents[passage.document_id].role_auteur if passage.document_id in documents else "unknown",
            "texte": passage.texte,
            "embedding": passage.embedding,
        }
        for passage in passages
    ]
    resultat = repondre(question, sources, chemin_modele)

    enregistrement = QuestionLitige(
        case_id=dossier.case_id,
        question=question,
        answer_status=resultat["answer_status"],
        answer=resultat["answer"],
        value=resultat.get("value"),
    )
    db.session.add(enregistrement)
    db.session.flush()

    passages_par_id = {passage.chunk_id: passage for passage in passages}
    citations: list[dict[str, Any]] = []
    for citation in resultat.get("citations", []):
        passage = passages_par_id.get(citation.get("chunk_id"))
        extrait = citation.get("quote", "")
        if passage is None or not extrait or extrait not in passage.texte:
            continue
        db.session.add(
            CitationLitige(
                question_id=enregistrement.id,
                chunk_id=passage.chunk_id,
                citation=extrait,
            )
        )
        citations.append(
            {"document_id": str(passage.document_id), "quote": extrait, "chunk_id": passage.chunk_id}
        )

    db.session.commit()
    return {
        "id": enregistrement.id,
        "answer_status": resultat["answer_status"],
        "answer": resultat["answer"],
        "value": resultat.get("value"),
        "citations": citations,
        "retrieval": resultat.get("retrieval", {"items": [], "mode": "tfidf_local"}),
    }
