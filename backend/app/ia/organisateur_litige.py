"""Outils autonomes pour organiser les pièces d'un dossier de litige locatif.

Ce module est volontairement indépendant du RAG immobilier existant.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

TYPES = {
    "bail": ("bail", "contrat de location", "clause", "avenant"),
    "paiement": ("virement", "reçu", "recu", "paiement", "loyer payé", "quittance"),
    "etat_des_lieux": ("état des lieux", "etat des lieux", "inventaire", "inspection"),
    "reparation": ("réparation", "reparation", "travaux", "plombier", "fuite", "panne"),
    "avis": ("mise en demeure", "préavis", "preavis", "résiliation", "resiliation", "avis"),
    "declaration": ("je conteste", "je confirme", "selon moi", "je vous informe", "mon locataire", "mon propriétaire"),
    "correspondance": ("bonjour", "cordialement", "message", "email", "courriel"),
}
SUJETS = {
    "depot": ("caution", "dépôt", "depot", "retenue", "déduction", "deduction", "garantie locative"),
    "loyer_impaye": ("loyer impayé", "loyer impaye", "loyers dus", "retard de paiement", "loyer non payé"),
    "reparations": ("réparation", "reparation", "travaux", "fuite", "humidité", "humidite", "dégât", "degat"),
    "resiliation": ("résiliation", "resiliation", "fin du bail", "préavis", "preavis", "congé", "conge"),
    "charges": ("charge", "facture", "eau", "électricité", "electricite", "gaz"),
    "acces": ("accès", "acces", "entrer dans le logement", "visite du propriétaire"),
}
DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")


def classer_passage(texte: str, source: str = "") -> dict[str, Any]:
    """Attribue des étiquettes indicatives à un passage textuel."""
    contenu = _sans_accents(f"{texte.casefold()} {source.casefold().replace('_', ' ')}")
    types = [nom for nom, mots in TYPES.items() if any(_sans_accents(mot) in contenu for mot in mots)]
    sujets = [nom for nom, mots in SUJETS.items() if any(_sans_accents(mot) in contenu for mot in mots)]
    auteur = "locataire" if any(_sans_accents(m) in contenu for m in ("mon propriétaire", "je suis locataire", "je conteste")) else None
    methode = "contenu" if auteur else None
    if auteur is None and any(_sans_accents(m) in contenu for m in ("mon locataire", "je suis propriétaire", "je retiens")):
        auteur = "proprietaire"
        methode = "contenu"
    if auteur is None:
        nom = source.casefold()
        locataire = any(m in nom for m in ("locataire", "tenant", "reponse_locataire"))
        proprietaire = any(m in nom for m in ("proprietaire", "propriétaire", "bailleur", "landlord"))
        if locataire != proprietaire:
            auteur = "locataire" if locataire else "proprietaire"
            methode = "nom du fichier"
    dates = DATE_RE.findall(texte)
    dates.extend(_dates_en_lettres(texte))
    return {"types": types or ["a_classer"], "sujets": sujets, "auteur_attribue": auteur,
            "auteur_methode": methode, "dates": list(dict.fromkeys(dates))}


def _dates_en_lettres(texte: str) -> list[str]:
    """Repère les dates françaises écrites avec le nom du mois."""
    mois = {"janvier": "01", "février": "02", "fevrier": "02", "mars": "03", "avril": "04",
            "mai": "05", "juin": "06", "juillet": "07", "août": "08", "aout": "08",
            "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12", "decembre": "12"}
    resultat = []
    for match in re.finditer(r"\b(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b", texte, re.IGNORECASE):
        resultat.append(f"{match.group(1).zfill(2)}/{mois[match.group(2).casefold()]}/{match.group(3)}")
    return resultat


def _tokens(texte: str) -> set[str]:
    """Normalise les accents et les terminaisons courantes pour la recherche lexicale."""
    sans_accents = _sans_accents(texte)
    tokens = set(re.findall(r"[a-z0-9]+", sans_accents))
    stopwords = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "pour", "sur", "dans", "qui", "que", "quelles", "quels", "quelle", "quel", "est", "sont", "aux", "au", "avec", "mon", "ma", "mes", "votre", "vos", "concernent"}
    return {t[:-1] if len(t) > 4 and t.endswith("s") else t for t in tokens if t not in stopwords}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte.casefold()) if not unicodedata.combining(c))


def extraire_pdf(contenu: bytes, nom: str) -> list[dict[str, Any]]:
    """Extrait les passages d'un PDF textuel et conserve la page source."""
    if not contenu.startswith(b"%PDF-"):
        raise ValueError("Le fichier fourni n'est pas un PDF valide.")
    lecteur = PdfReader(__import__("io").BytesIO(contenu))
    if len(lecteur.pages) > 150:
        raise ValueError("Le PDF dépasse la limite de 150 pages.")
    passages = []
    for numero, page in enumerate(lecteur.pages, start=1):
        texte = (page.extract_text() or "").strip()
        for index in range(0, len(texte), 1100):
            segment = texte[index:index + 1100].strip()
            if segment:
                passages.append({"id": uuid.uuid4().hex, "source": nom, "page": numero, "texte": segment,
                                 **classer_passage(segment, nom)})
    if not passages:
        raise ValueError("Aucun texte extractible n'a été trouvé dans le PDF.")
    return passages


def rapport_dossier(nom: str, documents: list[dict[str, Any]], question: str = "") -> dict[str, Any]:
    """Construit un inventaire, une chronologie et des résultats avec citations."""
    passages = []
    for document in documents:
        for passage in document.get("passages", []):
            passages.append({**passage, **classer_passage(passage.get("texte", ""), passage.get("source", document.get("nom", "")))})
    termes = _tokens(question)
    def pertinence(p: dict[str, Any]) -> int:
        tokens = _tokens(p["texte"])
        return len(termes & tokens)
    tries = sorted(passages, key=lambda p: (pertinence(p), len(p.get("dates", []))), reverse=True)
    dates = []
    for passage in passages:
        for date in passage.get("dates", []):
            formats = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%y", "%d.%m.%y")
            parsed = None
            for fmt in formats:
                parsed = _date_valide(date, fmt)
                if parsed:
                    break
            if parsed is None:
                continue
            dates.append((parsed, {"date": date, "citation": passage["texte"], "source": passage["source"], "page": passage["page"]}))
    return {
        "nom": nom,
        "inventaire": [{"nom": d["nom"], "passages": len(d["passages"])} for d in documents],
        "chronologie": [item for _, item in sorted(dates, key=lambda item: item[0])],
        "comptes_parties": [{"auteur": p["auteur_attribue"], "auteur_methode": p.get("auteur_methode"),
                              "citation": p["texte"], "source": p["source"], "page": p["page"]}
                            for p in passages if p.get("auteur_attribue")],
        "resultats": [{"citation": p["texte"], "source": p["source"], "page": p["page"],
                       "types": p["types"], "sujets": p["sujets"]} for p in tries[:8] if not question or pertinence(p) > 0],
        "questions_a_revoir": ["La date et le montant sont-ils confirmés par une pièce indépendante ?",
                               "Les parties décrivent-elles cet événement de la même façon ?"],
        "moteurs": {"classification": "règles locales de repli", "reclassement": "recherche lexicale locale",
                    "generation": "rapport structuré sans décision juridique"},
        "limite": "Ce rapport organise des passages; il ne détermine pas qui a raison en droit.",
    }


def dossier_dir(instance_path: str, user_id: str) -> Path:
    """Retourne le répertoire privé de l'utilisateur pour ce module autonome."""
    chemin = Path(instance_path) / "dossiers_litige" / str(user_id)
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def _date_valide(valeur: str, format_: str) -> datetime | None:
    try:
        return datetime.strptime(valeur, format_)
    except ValueError:
        return None
