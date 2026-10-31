"""Analyseur documentaire, OCR et vérificateur de complétude de contrats immobiliers en Tunisie.

Ce module extrait et vérifie :
- Le texte des contrats PDF et documents scannés,
- La pagination (détection des sauts de numérotation et des pages manquantes ou vides),
- Les dates clés, les noms des parties et les mentions de signatures/légalisation,
- Les champs obligatoires et champs vides à compléter,
- La complétude par rapport aux checklists tunisiennes officielles (location/vente).
"""

from __future__ import annotations

import io
import re
from typing import Any

from pypdf import PdfReader

from app.ia.rag.checklists import auditer_dossier


def extraire_texte_pdf(flux_pdf: bytes | io.BytesIO) -> list[dict[str, Any]]:
    """Extrait le texte d'un PDF page par page avec des métadonnées de structure.

    Args:
        flux_pdf: Octets du fichier PDF ou flux BytesIO.

    Returns:
        list[dict[str, Any]]: Liste des pages avec leur index, texte extrait,
            longueur et indicateur de page vide.
    """
    if isinstance(flux_pdf, bytes):
        flux = io.BytesIO(flux_pdf)
    else:
        flux = flux_pdf

    lecteur = PdfReader(flux)
    pages: list[dict[str, Any]] = []

    for index, page in enumerate(lecteur.pages, start=1):
        texte = page.extract_text() or ""
        texte_propre = texte.strip()
        est_vide = len(texte_propre) < 15

        pages.append({
            "numero_physique": index,
            "texte": texte_propre,
            "longueur": len(texte_propre),
            "est_vide": est_vide,
        })

    return pages


def decouper_en_chunks(
    pages: list[dict[str, Any]],
    taille_chunk: int = 500,
    chevauchement: int = 80,
) -> list[dict[str, Any]]:
    """Découpe les pages d'un document en segments textuels (chunks) pour l'indexation RAG.

    Args:
        pages: Liste des pages extraites du document.
        taille_chunk: Nombre cible de caractères par segment.
        chevauchement: Nombre de caractères partagés entre segments consécutifs.

    Returns:
        list[dict[str, Any]]: Liste des chunks avec page source, texte et index.
    """
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for page in pages:
        texte = page.get("texte", "").strip()
        num_page = page.get("numero_physique", 1)
        if not texte:
            continue

        if len(texte) <= taille_chunk:
            chunks.append({
                "index": chunk_index,
                "page": num_page,
                "texte": texte,
                "taille": len(texte),
            })
            chunk_index += 1
        else:
            debut = 0
            while debut < len(texte):
                fin = min(len(texte), debut + taille_chunk)
                segment = texte[debut:fin].strip()
                if segment:
                    chunks.append({
                        "index": chunk_index,
                        "page": num_page,
                        "texte": segment,
                        "taille": len(segment),
                    })
                    chunk_index += 1
                if fin >= len(texte):
                    break
                debut += taille_chunk - chevauchement

    return chunks


def detecter_sauts_numerotation(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Détecte les numéros de pages imprimés et repère les éventuels sauts ou pages manquantes.

    Selon le guide pratique : « Comparer le nombre de pages du fichier avec la numérotation
    visible sur les pages. Repérer les sauts de numérotation, les pages vides ou illisibles. »

    Args:
        pages: Liste des pages extraites.

    Returns:
        dict[str, Any]: Analyse de la pagination avec numéros détectés, sauts constatés et alertes.
    """
    total_physique = len(pages)
    numeros_detectes: list[int] = []
    motif_page = re.compile(
        r"(?:page|p\.)\s*(\d+)(?:\s*(?:sur|/|\-)\s*(\d+))?|"
        r"(\d+)\s*(?:sur|/)\s*(\d+)|"
        r"(?:صفحة)\s*(\d+)(?:\s*(?:من|/)\s*(\d+))?",
        re.IGNORECASE,
    )

    total_annonce: int | None = None

    for page in pages:
        match = motif_page.search(page["texte"])
        if match:
            groupes = [g for g in match.groups() if g is not None]
            if groupes:
                try:
                    num = int(groupes[0])
                    numeros_detectes.append(num)
                    page["numero_imprime"] = num
                    if len(groupes) >= 2:
                        total_annonce = int(groupes[1])
                except ValueError:
                    pass

    sauts: list[int] = []
    if len(numeros_detectes) >= 2:
        for i in range(len(numeros_detectes) - 1):
            actuel = numeros_detectes[i]
            suivant = numeros_detectes[i + 1]
            if suivant > actuel + 1:
                for manque in range(actuel + 1, suivant):
                    sauts.append(manque)

    pages_vides = [p["numero_physique"] for p in pages if p["est_vide"]]

    alertes: list[str] = []
    if sauts:
        alertes.append(
            f"Attention : saut de numérotation détecté. Page(s) imprimée(s) manquante(s) : {', '.join(map(str, sauts))}."
        )
    if pages_vides:
        alertes.append(
            f"Attention : page(s) vide(s) ou illisible(s) détectée(s) : page(s) {', '.join(map(str, pages_vides))}."
        )
    if total_annonce and total_annonce > total_physique:
        alertes.append(
            f"Le document mentionne {total_annonce} pages, mais le fichier n'en comporte que {total_physique}."
        )

    return {
        "total_physique": total_physique,
        "total_annonce": total_annonce,
        "numeros_detectes": numeros_detectes,
        "sauts_numerotation": sauts,
        "pages_vides": pages_vides,
        "alertes": alertes,
        "pagination_conforme": len(sauts) == 0 and len(pages_vides) == 0,
    }


def extraire_champs_contrat(texte_global: str) -> dict[str, Any]:
    """Extrait les champs essentiels et repère les mentions non complétées (champs vides).

    Args:
        texte_global: Texte complet du contrat assemblé.

    Returns:
        dict[str, Any]: Données identifiées (parties, loyer/prix, caution, durée, signatures, champs vides).
    """
    texte_lower = texte_global.lower()

    # Détection des montants (TND / Dinars)
    motif_montant = re.compile(
        r"(\d+(?:[\s.,]\d+)?)\s*(?:dt|tnd|dinars?|دينار|د\.ت)",
        re.IGNORECASE,
    )
    montants = motif_montant.findall(texte_global)

    # Détection des dates
    motif_date = re.compile(
        r"\b(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})\b",
    )
    dates = motif_date.findall(texte_global)

    # Détection des pièces d'identité (CIN tunisienne à 8 chiffres)
    motif_cin = re.compile(r"\bcin\s*(?:n[°o.]?)?\s*:?\s*(\d{8})\b|بطاقة\s*التعريف\s*(?:عدد)?\s*:?\s*(\d{8})", re.IGNORECASE)
    cins = [c[0] or c[1] for c in motif_cin.findall(texte_global)]

    # Détection des mentions de signature et de légalisation municipale
    mots_signature = [
        "lu et approuvé", "signature", "bailleur", "preneur", "vendeur", "acquéreur",
        "التعريف بالإمضاء", "بلدية", "إمضاء", "توقيع", "شهادة صحة إمضاء",
    ]
    mentions_signature = [m for m in mots_signature if m in texte_lower]
    a_signature = len(mentions_signature) >= 2

    # Détection des références à des annexes
    motif_annexes = re.compile(r"(?:annexe|état des lieux|inventaire|ملحق|محضر معاينة)\s*([A-Za-z0-9\-]+)?", re.IGNORECASE)
    annexes_citees = [match.group(0).strip() for match in motif_annexes.finditer(texte_global)]

    # Détection des champs vides ou à compléter (pointillés, underscores, crochets vides)
    motif_champs_vides = re.compile(r"(?:_{3,}|\.{3,}|\[\s*\]|\(à compléter\))")
    nb_champs_vides = len(motif_champs_vides.findall(texte_global))

    # Type de transaction
    est_vente = any(m in texte_lower for m in ["vente", "achat", "acquéreur", "vendeur", "titre bleu", "377", "بيع", "شراء"])
    type_transaction = "vente" if est_vente else "location"

    return {
        "type_transaction": type_transaction,
        "montants_trouves": montants,
        "dates_trouvees": dates,
        "cins_trouvees": cins,
        "mentions_signature": mentions_signature,
        "signature_detectee": a_signature,
        "annexes_citees": list(set(annexes_citees)),
        "nb_champs_vides": nb_champs_vides,
    }


def verifier_completude_contrat(
    flux_ou_texte: bytes | str,
    transaction_forcee: str | None = None,
    langue: str = "fr",
) -> dict[str, Any]:
    """Exécute l'analyse documentaire complète et vérifie la complétude du dossier.

    Args:
        flux_ou_texte: Contenu du fichier PDF (bytes) ou chaîne de texte brut.
        transaction_forcee: 'location' ou 'vente', ou None pour détection automatique.
        langue: 'fr' ou 'ar'.

    Returns:
        dict[str, Any]: Rapport complet avec pagination, champs extraits, anomalies,
            audit checklist et recommandations.
    """
    if isinstance(flux_ou_texte, bytes):
        pages = extraire_texte_pdf(flux_ou_texte)
        texte_global = "\n\n".join(p["texte"] for p in pages)
        analyse_pagination = detecter_sauts_numerotation(pages)
    else:
        texte_global = flux_ou_texte
        pages = [{
            "numero_physique": 1,
            "texte": texte_global,
            "longueur": len(texte_global),
            "est_vide": len(texte_global.strip()) < 15,
        }]
        analyse_pagination = {
            "total_physique": 1,
            "total_annonce": None,
            "numeros_detectes": [1],
            "sauts_numerotation": [],
            "pages_vides": [],
            "alertes": [],
            "pagination_conforme": True,
        }

    champs = extraire_champs_contrat(texte_global)
    transaction = transaction_forcee or champs["type_transaction"]

    # Éléments détectés pour la checklist
    elements_presents: list[str] = []
    if champs["cins_trouvees"]:
        elements_presents.append("cin_proprietaire" if transaction == "location" else "cin_vendeur")
        if len(champs["cins_trouvees"]) >= 2:
            elements_presents.append("cin_locataire" if transaction == "location" else "cin_acheteur")

    if champs["montants_trouves"]:
        elements_presents.append("loyer_et_caution" if transaction == "location" else "quitus_fiscal_et_paiement")

    if champs["signature_detectee"]:
        elements_presents.append("signatures_legalisation" if transaction == "location" else "acte_redige_habilite")

    # Contrat lui-même
    elements_presents.append("contrat_location" if transaction == "location" else "acte_redige_habilite")

    audit_checklist = auditer_dossier(
        transaction=transaction,
        elements_fournis=elements_presents,
        langue=langue,
    )

    alertes_globales = list(analyse_pagination["alertes"])
    if champs["nb_champs_vides"] > 0:
        alertes_globales.append(
            f"{champs['nb_champs_vides']} champ(s) non renseigné(s) ou avec des pointillés détecté(s) dans le document."
        )
    if not champs["signature_detectee"]:
        alertes_globales.append(
            "Aucune mention explicite de signature ou de légalisation municipale (Baladiya) n'a été trouvée."
        )

    est_complet = (
        analyse_pagination["pagination_conforme"]
        and champs["nb_champs_vides"] == 0
        and len(champs["cins_trouvees"]) >= 2
        and len(champs["montants_trouves"]) >= 1
    )

    chunks = decouper_en_chunks(pages)

    return {
        "statut_document": "valide" if est_complet else "a_completer",
        "transaction": transaction,
        "pagination": analyse_pagination,
        "champs_extraits": champs,
        "alertes": alertes_globales,
        "audit_checklist": audit_checklist,
        "chunks": chunks,
        "texte_integral": texte_global,
        "pages": pages,
        "recommandations_diwan": [
            "Vérifier la concordance exacte entre les noms du contrat et les pièces d'identité (CIN).",
            "Faire légaliser les signatures auprès de la municipalité (Baladiya).",
            "Enregistrer le document auprès de la Recette des Finances dans un délai de 60 jours.",
            "Conserver une copie intégrale avec les reçus officiels délivrés.",
        ],
    }
