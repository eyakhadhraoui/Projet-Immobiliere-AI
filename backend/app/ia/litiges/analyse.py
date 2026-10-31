"""Classement prudent, dates explicites, recherche et réponses avec preuves."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TYPES_PREUVE: dict[str, tuple[str, ...]] = {
    "payment_record": ("virement", "reçu", "recu", "paiement", "quittance", "payé", "paye", "transaction bancaire"),
    "lease_clause": ("bail", "contrat de location", "loyer mensuel", "caution", "clause", "avenant"),
    "condition_report": ("état des lieux", "etat des lieux", "inventaire", "inspection", "remise des clés", "remise des cles"),
    "repair_record": ("réparation", "reparation", "travaux", "plombier", "fuite", "facture d'intervention"),
    "notice": ("mise en demeure", "préavis", "preavis", "résiliation", "resiliation", "congé", "conge"),
    "party_statement": ("je conteste", "je confirme", "selon moi", "je déclare", "je declare", "à mon avis"),
    "correspondence": ("bonjour", "cordialement", "email", "courriel", "message", "objet:"),
}
SUJETS: dict[str, tuple[str, ...]] = {
    "deposit": ("dépôt", "depot", "caution", "retenue", "garantie locative"),
    "rent_arrears": ("loyer impayé", "loyer impaye", "loyers dus", "retard de paiement", "arriéré"),
    "repairs": ("réparation", "reparation", "travaux", "fuite", "humidité", "humidite", "dégât", "degat"),
    "notice": ("résiliation", "resiliation", "fin du bail", "préavis", "preavis", "congé", "conge"),
    "utilities": ("charge", "facture", "eau", "électricité", "electricite", "gaz"),
    "access": ("accès", "acces", "entrer dans le logement", "visite du propriétaire"),
}
ROLES_AUTEUR = {"tenant", "landlord", "both_parties", "payment_provider", "contractor", "unknown", "other"}
MOIS = {
    "january": 1, "janvier": 1, "february": 2, "février": 2, "fevrier": 2,
    "march": 3, "mars": 3, "april": 4, "avril": 4, "may": 5, "mai": 5,
    "june": 6, "juin": 6, "july": 7, "juillet": 7, "august": 8,
    "août": 8, "aout": 8, "september": 9, "septembre": 9, "october": 10,
    "octobre": 10, "november": 11, "novembre": 11, "december": 12,
    "décembre": 12, "decembre": 12,
}
DATE_NUM_RE = re.compile(r"\b(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[./-](\d{1,2})[./-](\d{4}))\b")
_mois_pattern = "|".join(re.escape(mois) for mois in sorted(MOIS, key=len, reverse=True))
DATE_MOIS_RE = re.compile(rf"\b(\d{{1,2}})\s+({_mois_pattern})\s+(\d{{4}})\b", re.IGNORECASE)
MONTANT_RE = re.compile(r"(?<!\w)(\d{1,3}(?:[ .\u00a0]\d{3})+(?:[,.]\d{1,2})?|\d+(?:[,.]\d{1,2})?)\s*(?:TND|DT|EUR|€|USD|\$)", re.IGNORECASE)


def normaliser(texte: str) -> str:
    """Normalise accents et casse uniquement pour les comparaisons, sans toucher aux sources."""
    return "".join(c for c in unicodedata.normalize("NFKD", texte.casefold()) if not unicodedata.combining(c))


def classifier(texte: str) -> tuple[str, str, float]:
    """Propose un type et un sujet par règles locales, jamais comme vérité vérifiée."""
    contenu = normaliser(texte)
    types = [(cle, sum(normaliser(mot) in contenu for mot in mots)) for cle, mots in TYPES_PREUVE.items()]
    sujets = [(cle, sum(normaliser(mot) in contenu for mot in mots)) for cle, mots in SUJETS.items()]
    type_preuve, score_type = max(types, key=lambda item: item[1])
    sujet, score_sujet = max(sujets, key=lambda item: item[1])
    score = min(0.95, 0.55 + 0.1 * max(score_type, score_sujet)) if max(score_type, score_sujet) else 0.0
    return (type_preuve if score_type else "other", sujet if score_sujet else "other", score)


def extraire_dates(texte: str, attribution: str = "unknown") -> list[dict[str, Any]]:
    """Retourne uniquement les dates complètes, valides et textuellement présentes."""
    candidates: list[tuple[int, date, str]] = []
    for match in DATE_NUM_RE.finditer(texte):
        if match.group(1):
            year, month, day = map(int, match.group(1, 2, 3))
        else:
            day, month, year = map(int, match.group(4, 5, 6))
            # Sans contexte de langue, 05/06/YYYY peut signifier 5 juin ou 6 mai.
            if day <= 12 and month <= 12:
                continue
        try:
            candidates.append((match.start(), date(year, month, day), match.group(0)))
        except ValueError:
            continue
    for match in DATE_MOIS_RE.finditer(texte):
        month_text = normaliser(match.group(2))
        month = next((v for k, v in MOIS.items() if normaliser(k) == month_text), None)
        if month is None:
            continue
        try:
            candidates.append((match.start(), date(int(match.group(3)), month, int(match.group(1))), match.group(0)))
        except ValueError:
            continue
    result: list[dict[str, Any]] = []
    seen: set[date] = set()
    for start, day, original in sorted(candidates):
        if day in seen:
            continue
        seen.add(day)
        left = max(texte.rfind(".", 0, start), texte.rfind("!", 0, start), texte.rfind("?", 0, start), texte.rfind("\n", 0, start)) + 1
        stops = [pos for char in (".", "!", "?", "\n") if (pos := texte.find(char, start + len(original))) >= 0]
        right = min(stops) + 1 if stops else min(len(texte), start + len(original) + 300)
        result.append({"date": day, "source_text": texte[left:right].strip(), "attribution": attribution, "verified": False})
    return result


@lru_cache(maxsize=2)
def _charger_modele_local(path: str):
    """Charge un encodeur uniquement depuis un chemin local configuré explicitement."""
    dossier = Path(path)
    if not dossier.is_dir():
        return None
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(str(dossier), device="cpu", local_files_only=True)
    except Exception:
        return None


def embedding_local(texte: str, chemin_modele: str | None) -> list[float] | None:
    """Calcule un embedding avec un modèle déjà présent localement, sans téléchargement."""
    if not chemin_modele:
        return None
    modele = _charger_modele_local(chemin_modele)
    if modele is None:
        return None
    return [float(x) for x in modele.encode(texte, normalize_embeddings=True).tolist()]


def modele_semantique_disponible(chemin_modele: str | None) -> bool:
    """Indique si le modèle configuré peut réellement être chargé depuis le disque local."""
    return bool(chemin_modele and _charger_modele_local(chemin_modele))


def rechercher(question: str, passages: list[dict[str, Any]], chemin_modele: str | None = None, limite: int = 5) -> dict[str, Any]:
    """Recherche hybride dans une liste qui doit déjà appartenir à un dossier unique."""
    if not passages or not question.strip():
        return {"items": [], "mode": "tfidf_local", "semantic_available": False}
    textes = [str(item.get("texte", "")) for item in passages]
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", max_features=20_000)
        matrix = vectorizer.fit_transform([question, *textes])
        lexical = cosine_similarity(matrix[0:1], matrix[1:]).ravel().tolist()
    except ValueError:
        lexical = [0.0] * len(passages)
    q_vec = embedding_local(question, chemin_modele)
    semantic: list[float] | None = None
    if q_vec is not None:
        semantic = []
        for item in passages:
            p_vec = item.get("embedding")
            if not p_vec:
                p_vec = embedding_local(str(item.get("texte", "")), chemin_modele)
            if not p_vec or len(p_vec) != len(q_vec):
                semantic.append(0.0)
                continue
            semantic.append(max(0.0, sum(a * b for a, b in zip(q_vec, p_vec))))
    qnorm = normaliser(question)
    scores = []
    for index, passage in enumerate(passages):
        exact = 0.12 if qnorm and qnorm in normaliser(textes[index]) else 0.0
        # Reranking uses the semantic score only when the local model is available.
        score = (0.65 * lexical[index] + 0.35 * semantic[index] if semantic is not None else lexical[index]) + exact
        scores.append((score, passage))
    selected = [{**p, "score": round(float(score), 4)} for score, p in sorted(scores, key=lambda x: x[0], reverse=True)[:limite] if score >= 0.025]
    return {"items": selected, "mode": "hybride_local" if semantic is not None else "tfidf_local", "semantic_available": semantic is not None}


def valider_citation(texte_source: str, citation: str) -> bool:
    """Accepte seulement une citation non vide reproduite littéralement dans la source."""
    return bool(citation.strip()) and citation in texte_source


def repondre(question: str, passages: list[dict[str, Any]], chemin_modele: str | None = None) -> dict[str, Any]:
    """Construit une réponse factuelle extractive, s'abstenant si la preuve manque."""
    retrieval = rechercher(question, passages, chemin_modele)
    sources = retrieval["items"]
    norm_question = normaliser(question)
    depot = any(term in norm_question for term in ("depot", "caution", "garantie"))
    remboursement = any(term in norm_question for term in ("rembourse", "restitue", "remboursement"))
    if depot and remboursement:
        remboursements = [p for p in sources if any(t in normaliser(str(p["texte"])) for t in ("remboursé", "remboursee", "restitué", "restituee", "remboursement effectué"))]
        if not remboursements:
            return {"answer_status": "insufficient_evidence", "answer": "Les passages importés ne permettent pas d’établir qu’un remboursement du dépôt a eu lieu. Une preuve du versement initial ne prouve pas à elle seule un remboursement.", "value": None, "citations": [], "retrieval": retrieval}
    account_roles = {p.get("role_auteur") for p in sources}
    if "tenant" in account_roles and "landlord" in account_roles and _opposition_detectee(sources):
        return {
            "answer_status": "conflicting_accounts",
            "answer": "Les documents contiennent des déclarations opposées sur le point demandé. Elles sont présentées sans déterminer laquelle est exacte.",
            "value": None,
            "citations": _citations(sources, roles={"tenant", "landlord"}),
            "retrieval": retrieval,
        }
    if not sources:
        return {"answer_status": "insufficient_evidence", "answer": "Aucun passage suffisamment pertinent n’a été retrouvé dans ce dossier. Cela ne prouve pas que la pièce n’existe pas.", "value": None, "citations": [], "retrieval": retrieval}
    citations = _citations_pertinentes(question, sources)
    value = _extraire_valeur(question, sources)
    if value:
        answer = f"Les documents importés mentionnent {value}. Cette mention apparaît dans les passages cités et n'a pas été authentifiée."
    elif _question_definition(question) and citations:
        quotes = " ".join(citation["quote"] for citation in citations)
        normalized_quotes = normaliser(quotes)
        if "inventaire" in norm_question and any(term in normalized_quotes for term in ("etat des lieux d'entree", "etat des lieux d entree")):
            description = next((item["quote"] for item in citations if "inventaire" in normaliser(item["quote"])), citations[0]["quote"])
            signature = next((item["quote"] for item in citations if "signe" in normaliser(item["quote"]) and "parties" in normaliser(item["quote"])), None)
            detail = f" Le document précise : « {description} »"
            if signature:
                detail += f" Il indique aussi : « {signature} »"
            answer = "Dans ce dossier, l’inventaire d’entrée désigne le rapport d’état des lieux établi au début de la location." + detail + ". Cette pièce n’est pas authentifiée."
        else:
            answer = f"Les documents décrivent le terme demandé ainsi : « {citations[0]['quote']} ». Cette information n'a pas été authentifiée."
    elif citations:
        first_source = str(sources[0].get("nom_fichier", "le document importé"))
        answer = f"D’après le document {first_source} : « {citations[0]['quote']} ». Cette mention n'a pas été authentifiée."
    else:
        answer = "Aucun passage pertinent contenant une réponse vérifiable n'a été retrouvé dans ce dossier."
    return {
        "answer_status": "supported",
        "answer": answer,
        "value": value,
        "citations": citations,
        "retrieval": retrieval,
    }


def _citations(passages: list[dict[str, Any]], roles: set[str] | None = None) -> list[dict[str, str]]:
    result = []
    for p in passages:
        if roles and p.get("role_auteur") not in roles:
            continue
        quote = str(p.get("texte", ""))[:1200]
        if valider_citation(str(p.get("texte", "")), quote):
            result.append({"chunk_id": str(p["chunk_id"]), "quote": quote})
    return result


def _question_definition(question: str) -> bool:
    q = normaliser(question)
    return any(expression in q for expression in ("c'est quoi", "c est quoi", "qu'est-ce que", "qu est ce que", "que signifie", "definition de", "definir"))


def _citations_pertinentes(question: str, passages: list[dict[str, Any]], limite: int = 3) -> list[dict[str, str]]:
    """Retourne des phrases sources exactes, au lieu de citer des pages entieres."""
    candidats: list[tuple[dict[str, Any], str]] = []
    for passage in passages:
        texte = str(passage.get("texte", ""))
        for phrase in re.split(r"(?<=[.!?])\s+|\n+", texte):
            phrase = phrase.strip(" \t\r\n-•")
            if len(phrase) >= 35:
                candidats.append((passage, phrase))
    if not candidats:
        return _citations(passages[:1])
    question_normalisee = normaliser(question)
    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode").fit_transform(
            [question, *(phrase for _, phrase in candidats)]
        )
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel().tolist()
    except ValueError:
        scores = [0.0] * len(candidats)
    termes = {mot for mot in re.findall(r"[a-z0-9]{3,}", question_normalisee) if mot not in {"quoi", "est", "que", "une", "dans", "pour", "sur", "les", "des"}}
    classement = []
    for index, (passage, phrase) in enumerate(candidats):
        texte_normalise = normaliser(phrase)
        recouvrement = sum(terme in texte_normalise for terme in termes)
        score = scores[index] + min(recouvrement, 4) * 0.035
        if score > 0:
            classement.append((score, passage, phrase))
    classement.sort(key=lambda item: item[0], reverse=True)
    resultat: list[dict[str, str]] = []
    vus: set[tuple[str, str]] = set()
    for _, passage, phrase in classement:
        cle = (str(passage.get("chunk_id", "")), phrase)
        if cle in vus:
            continue
        vus.add(cle)
        resultat.append({"chunk_id": cle[0], "quote": phrase})
        if len(resultat) >= limite:
            break
    return resultat


def _opposition_detectee(passages: list[dict[str, Any]]) -> bool:
    tenant = " ".join(normaliser(str(p["texte"])) for p in passages if p.get("role_auteur") == "tenant")
    landlord = " ".join(normaliser(str(p["texte"])) for p in passages if p.get("role_auteur") == "landlord")
    positions = (
        ({"pendant la location", "durant la location", "pendant le bail", "durant le bail", "causé pendant", "apparu pendant"},
         {"deja avant", "existait avant", "etait deja present", "a l'entree", "avant la location", "avant le bail"}),
        ({"a ete paye", "a payé", "verse", "virement effectue", "a remboursé", "a rembourse"},
         {"n'a pas ete paye", "pas payé", "non payé", "non paye", "pas rembourse", "pas remboursé", "aucun remboursement"}),
    )
    for position_a, position_b in positions:
        if any(normaliser(signal) in tenant for signal in position_a) and any(normaliser(signal) in landlord for signal in position_b):
            return True
        if any(normaliser(signal) in landlord for signal in position_a) and any(normaliser(signal) in tenant for signal in position_b):
            return True
    negations = ("pas", "jamais", "aucun", "n'a pas", "ne ... pas")
    if any(x in tenant for x in negations) != any(x in landlord for x in negations):
        shared = set(re.findall(r"[a-z0-9]{4,}", tenant)) & set(re.findall(r"[a-z0-9]{4,}", landlord))
        return len(shared) >= 2
    return False


def _extraire_valeur(question: str, passages: list[dict[str, Any]]) -> str | None:
    normalized_question = normaliser(question)
    if any(t in normalized_question for t in ("date", "quand", "quel jour")):
        for passage in passages:
            dates = extraire_dates(str(passage.get("texte", "")))
            if dates:
                return dates[0]["date"].isoformat()
    if not any(t in normalized_question for t in ("montant", "combien", "loyer", "depot", "caution", "somme")):
        return None
    for passage in passages:
        match = MONTANT_RE.search(str(passage.get("texte", "")))
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None
