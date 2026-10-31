"""Moteur de recherche contextuelle (Retriever RAG) pour le droit immobilier tunisien."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

from app.ia.rag.corpus import obtenir_corpus

STOPWORDS_FR = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a", "à", "en", "dans",
    "pour", "par", "sur", "avec", "sans", "ce", "cet", "cette", "ces", "mon", "ma", "mes", "ton", "ta",
    "tes", "son", "sa", "ses", "qui", "que", "quoi", "dont", "est", "sont", "être", "avoir", "faire",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "me", "te", "se", "y", "ne", "pas", "plus",
}

STOPWORDS_AR = {
    "في", "من", "إلى", "على", "عن", "مع", "هذا", "هذه", "ذلك", "تلك", "هو", "هي", "هم", "هن",
    "أن", "إن", "كان", "كانت", "يكون", "ما", "ماذا", "هل", "كيف", "أين", "متى", "كم", "الذي", "التي",
    "الذين", "كل", "بعض", "غير", "قد", "لقد", "ثم", "أو", "و", "يا", "لا", "لم", "لن", "إلا",
}


def normaliser_texte(texte: str) -> str:
    """Normalise une chaîne en supprimant les accents, la ponctuation et en unifiant l'arabe.

    Args:
        texte: Texte brut.

    Returns:
        str: Texte normalisé en minuscules.
    """
    if not texte:
        return ""

    # Décompose les accents puis supprime uniquement les marques combinatoires.
    # Sans cette étape, le filtre de ponctuation remplace les accents par des espaces
    # (ex. « préparer » devenait « pre parer ») et la recherche lexicale perd ses termes.
    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.combining(caractere)
    )

    # Normalisation spécifique arabe : unifier alif, ta marbouta, ya
    texte = re.sub(r"[\u064B-\u065F\u0670]", "", texte)  # supprimer les tashkeel / voyelles brèves
    texte = re.sub(r"[إأآا]", "ا", texte)
    texte = re.sub(r"ة", "ه", texte)
    texte = re.sub(r"ى", "ي", texte)

    # Remplacer ponctuation par des espaces et mettre en minuscules
    texte = re.sub(r"[^\w\s\u0600-\u06FF]", " ", texte.lower())
    return " ".join(texte.split())


def tokeniser(texte: str) -> list[str]:
    """Découpe un texte en mots significatifs filtrés des stopwords.

    Args:
        texte: Texte à analyser.

    Returns:
        list[str]: Liste des tokens significatifs.
    """
    texte_norm = normaliser_texte(texte)
    mots = texte_norm.split()
    tokens = [m for m in mots if len(m) > 1 and m not in STOPWORDS_FR and m not in STOPWORDS_AR]
    return tokens


def detecter_langue(texte: str) -> str:
    """Détecte si un texte est principalement en arabe ou en français.

    Args:
        texte: Requête de l'utilisateur.

    Returns:
        str: 'ar' ou 'fr'.
    """
    nb_arabe = len(re.findall(r"[\u0600-\u06FF]", texte))
    nb_latin = len(re.findall(r"[a-zA-Z]", texte))
    return "ar" if nb_arabe > nb_latin else "fr"


class RAGRetriever:
    """Retriever vectoriel et sémantique pour les textes immobiliers tunisiens."""

    def __init__(self, corpus: list[dict[str, Any]] | None = None) -> None:
        """Initialise le retriever avec le corpus documentaire.

        Args:
            corpus: Documents à indexer, ou ``None`` pour utiliser le corpus officiel.
        """
        self.corpus = corpus if corpus is not None else obtenir_corpus()
        self._index: list[dict[str, Any]] = []
        self._idf: dict[str, float] = {}
        self._construire_index()

    def _construire_index(self) -> None:
        """Calcule les fréquences de termes et l'IDF pour chaque document."""
        nb_docs = max(1, len(self.corpus))
        df: Counter[str] = Counter()

        for doc in self.corpus:
            texte_complet = (
                f"{doc['titre_fr']} {doc['titre_ar']} {doc['contenu_fr']} {doc['contenu_ar']} "
                f"{' '.join(doc.get('tags', []))} {doc.get('theme', '')}"
            )
            tokens = tokeniser(texte_complet)
            tf = Counter(tokens)
            doc_unique = set(tokens)
            for mot in doc_unique:
                df[mot] += 1

            self._index.append({
                "doc": doc,
                "tf": tf,
                "total_tokens": max(1, len(tokens)),
            })

        for mot, freq in df.items():
            self._idf[mot] = math.log((nb_docs + 1) / (freq + 1)) + 1.0

    def chercher(
        self,
        requete: str,
        transaction_filtre: str | None = None,
        langue: str | None = None,
        top_k: int = 4,
        documents_utilisateur: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Recherche les documents et extraits les plus pertinents pour une requête.

        Prend en compte à la fois les documents importés par l'utilisateur (PDFs, contrats)
        et la base documentaire légale tunisienne.

        Args:
            requete: Message ou question de l'utilisateur.
            transaction_filtre: Filtrer sur 'location' ou 'vente' si précisé.
            langue: Langue préférée pour l'affichage ('fr' ou 'ar').
            top_k: Nombre maximal d'extraits à renvoyer.
            documents_utilisateur: Documents importés par l'utilisateur (avec texte ou chunks).

        Returns:
            list[dict[str, Any]]: Documents pertinents avec score et extraits adaptés.
        """
        if not langue:
            langue = detecter_langue(requete)

        tokens_req = tokeniser(requete)
        req_norm = normaliser_texte(requete)

        # 1. Recherche dans les documents utilisateurs importés (PDFs, scans, etc.)
        extraits_utilisateur: list[dict[str, Any]] = []
        if documents_utilisateur:
            for u_doc in documents_utilisateur:
                nom_fichier = u_doc.get("nom", "document.pdf")
                chunks = u_doc.get("chunks", [])
                if not chunks and u_doc.get("texte"):
                    chunks = [{"texte": u_doc["texte"], "page": 1, "index": 0}]

                for c in chunks:
                    c_texte = c.get("texte", "")
                    c_page = c.get("page", 1)
                    c_tokens = tokeniser(c_texte)
                    if not c_tokens:
                        continue
                    tf_chunk = Counter(c_tokens)
                    score_chunk = 0.0
                    for token in tokens_req:
                        if token in tf_chunk:
                            poids = tf_chunk[token] / len(c_tokens)
                            score_chunk += poids * self._idf.get(token, 1.2)

                    # Bonus si le nom du fichier ou un mot de document est cité
                    if normaliser_texte(nom_fichier) in req_norm:
                        score_chunk += 0.8
                    elif any(m in req_norm for m in ["document", "pdf", "contrat", "avenant", "mon", "fichier"]):
                        score_chunk += 0.35

                    # Même si aucun mot ne matche, si l'utilisateur a 1 seul document et pose une question générale
                    if score_chunk == 0.0 and len(documents_utilisateur) == 1 and len(tokens_req) > 0:
                        score_chunk = 0.15

                    if score_chunk > 0:
                        extraits_utilisateur.append({
                            "id": f"usr_{nom_fichier}_p{c_page}_{c.get('index', 0)}",
                            "titre": nom_fichier,
                            "source": f"{nom_fichier} (Page {c_page})",
                            "contenu": c_texte,
                            "theme": "utilisateur",
                            "score": round(score_chunk * 1.6, 4),
                            "est_document_utilisateur": True,
                        })

            extraits_utilisateur.sort(key=lambda x: x["score"], reverse=True)

        if not tokens_req:
            # Si la requête est vide ou n'a que des stopwords, renvoyer les documents phares du thème
            resultats: list[dict[str, Any]] = []
            for item in self._index:
                doc = item["doc"]
                if transaction_filtre and doc.get("theme") not in (transaction_filtre, "general"):
                    continue
                resultats.append({
                    "id": doc["id"],
                    "titre": doc["titre_ar"] if langue == "ar" else doc["titre_fr"],
                    "source": doc["source"],
                    "contenu": doc["contenu_ar"] if langue == "ar" else doc["contenu_fr"],
                    "score": 0.5,
                })
                if len(resultats) >= top_k:
                    break
            return (extraits_utilisateur[:2] + resultats)[:top_k]

        scores_base: list[tuple[float, dict[str, Any]]] = []

        for item in self._index:
            doc = item["doc"]
            theme = doc.get("theme")

            # Filtrage optionnel par transaction
            if transaction_filtre and transaction_filtre != "general" and theme != transaction_filtre:
                penalite = 0.3
            else:
                penalite = 1.0

            tf = item["tf"]
            total = item["total_tokens"]

            score = 0.0
            for token in tokens_req:
                if token in tf:
                    poids_tf = tf[token] / total
                    idf = self._idf.get(token, 1.0)
                    score += poids_tf * idf

            # Bonus si le token correspond exactement à un tag clé
            tags = [normaliser_texte(t) for t in doc.get("tags", [])]
            for token in tokens_req:
                if token in tags:
                    score += 0.25

            score *= penalite

            if score > 0:
                scores_base.append((score, doc))

        scores_base.sort(key=lambda x: x[0], reverse=True)

        extraits_base: list[dict[str, Any]] = []
        for score, doc in scores_base[:top_k]:
            extraits_base.append({
                "id": doc["id"],
                "titre": doc["titre_ar"] if langue == "ar" else doc["titre_fr"],
                "source": doc["source"],
                "contenu": doc["contenu_ar"] if langue == "ar" else doc["contenu_fr"],
                "theme": doc.get("theme"),
                "score": round(score, 4),
            })

        # Combiner documents utilisateurs (en tête si pertinents) et corpus légal
        if extraits_utilisateur:
            tous = extraits_utilisateur[:2] + extraits_base[: max(1, top_k - len(extraits_utilisateur[:2]))]
            return tous[:top_k]

        return extraits_base[:top_k]
