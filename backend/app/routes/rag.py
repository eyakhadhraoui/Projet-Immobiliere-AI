"""Routes de l'assistant documentaire RAG immobilier (préfixe ``/api/rag``)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask.typing import ResponseReturnValue

from app.ia.rag.checklists import CHECKLIST_LOCATION, CHECKLIST_VENTE
from app.ia.rag.generateur import AssistantRAG
from app.ia.rag.documents_store import (
    DocumentRAGError,
    ajouter_pdf,
    lister_documents,
    supprimer_pdf,
    suggestions_pdf,
)
from app.securite import utilisateur_optionnel
from app.schemas.rag_schema import RagChatSchema

bp = Blueprint("rag", __name__, url_prefix="/api/rag")

_chat_schema = RagChatSchema()
_assistant = AssistantRAG()

SUGGESTIONS_QUESTIONS: dict[str, list[dict[str, str]]] = {
    "fr": [
        {
            "id": "q1",
            "titre": "Documents pour louer un appartement",
            "question": "Quels sont les documents obligatoires pour louer un appartement en Tunisie ?",
            "transaction": "location",
        },
        {
            "id": "q2",
            "titre": "Dossier location pour étudiant",
            "question": "Je suis étudiant : quels justificatifs et garanties me faut-il pour louer un studio ?",
            "transaction": "location",
        },
        {
            "id": "q3",
            "titre": "Légalisation et Recette des Finances",
            "question": "Où légaliser le contrat de location et combien coûte l'enregistrement à la recette des finances ?",
            "transaction": "location",
        },
        {
            "id": "q4",
            "titre": "Pièces obligatoires pour vendre",
            "question": "Quels sont les documents nécessaires pour vendre un bien immobilier en Tunisie ?",
            "transaction": "vente",
        },
        {
            "id": "q5",
            "titre": "Titre Bleu et avocat obligatoire",
            "question": "Pourquoi la rédaction de l'acte de vente par un avocat ou notaire est-elle obligatoire (Art. 377 bis) ?",
            "transaction": "vente",
        },
        {
            "id": "q6",
            "titre": "Quitus fiscal municipal (Zebla w Khrouba)",
            "question": "Qu'est-ce que le quitus de taxe municipale et qui doit le payer lors d'une vente ?",
            "transaction": "vente",
        },
        {
            "id": "q7",
            "titre": "Vérifier les pages d'un contrat",
            "question": "Comment bien vérifier les pages d'un contrat immobilier (sauts de numérotation, annexes, illisible) ?",
            "transaction": "general",
        },
        {
            "id": "q8",
            "titre": "Fiche Diwan et démarches en 5 étapes",
            "question": "Quelles sont les démarches générales recommandées par la fiche Diwan pour enregistrer un contrat ou un acte d'acquisition ?",
            "transaction": "general",
        },
    ],
    "ar": [
        {
            "id": "qa1",
            "titre": "وثائق كراء شقة في تونس",
            "question": "ما هي الوثائق اللازمة لكراء شقة أو منزل في تونس ؟",
            "transaction": "location",
        },
        {
            "id": "qa2",
            "titre": "كراء استوديو للطلبة والضامن",
            "question": "أنا طالب : ما هي الوثائق المطلوبة والضمانات لكراء استوديو جامعي ؟",
            "transaction": "location",
        },
        {
            "id": "qa3",
            "titre": "التعريف بالإمضاء والتسجيل بالقباضة",
            "question": "أين يتم التعريف بالإمضاء لعقد الكراء وما هي معاليم التسجيل بالقباضة المالية ؟",
            "transaction": "location",
        },
        {
            "id": "qa4",
            "titre": "الوثائق الضرورية لبيع عقار",
            "question": "ما هي الوثائق والإجراءات القانونية اللازمة لبيع عقار بتونس ؟",
            "transaction": "vente",
        },
        {
            "id": "qa5",
            "titre": "شهادة الملكية (الرسم العقاري) ومحرر العقد",
            "question": "هل يصح تحرير عقد البيع بدون محام لدى التعقيب وما هو الرسم العقاري Titre Bleu ؟",
            "transaction": "vente",
        },
        {
            "id": "qa6",
            "titre": "إبراء الذمة البلدي (الزبلة والخروبة)",
            "question": "ما هي شهادة إبراء الذمة البلدية من معلوم الزبلة والخروبة قبل البيع ؟",
            "transaction": "vente",
        },
        {
            "id": "qa7",
            "titre": "نصائح التثبت من صفحات العقد",
            "question": "كيف أتثبت من صفحات العقد والملاحق وفق الدليل العملي (انقطاع الترقيم والصفحات الناقصة) ؟",
            "transaction": "general",
        },
        {
            "id": "qa8",
            "titre": "دليل ديوان في 5 مراحل",
            "question": "ما هي المراحل العامة الخمس حسب دليل ديوان لإتمام عملية الكراء أو البيع العقاري ؟",
            "transaction": "general",
        },
    ],
}


@bp.post("/chat")
def chat_route() -> ResponseReturnValue:
    """Pose une question au chatbot RAG ou demande l'audit de son dossier.

    Returns:
        ResponseReturnValue: 200 avec réponse markdown, sources, transaction et audit.
    """
    donnees = _chat_schema.load(request.get_json() or {})
    langue_demande = donnees.get("langue")
    if langue_demande == "auto":
        langue_demande = None

    utilisateur = utilisateur_optionnel()
    try:
        resultat = _assistant.repondre(
            message=donnees["message"],
            transaction=donnees.get("transaction", "general"),
            elements_coches=donnees.get("elements_coches", []),
            langue_forcee=langue_demande,
            user_id=str(utilisateur.id) if utilisateur else None,
        )
    except ModuleNotFoundError as erreur:
        current_app.logger.exception("Dépendance RAG absente: %s", erreur.name)
        return jsonify({
            "error": "rag_dependances_manquantes",
            "message": "Le moteur PDF n'est pas installé dans l'environnement Python actif. Depuis backend, exécutez : .\\venv\\Scripts\\python.exe -m pip install -r requirements.txt, puis redémarrez le serveur.",
        }), 503
    return jsonify(resultat), 200


@bp.get("/documents")
def documents_route() -> ResponseReturnValue:
    """Liste le guide public et les PDF privés de la session connectée."""
    utilisateur = utilisateur_optionnel()
    try:
        return jsonify({"documents": lister_documents(str(utilisateur.id) if utilisateur else None)}), 200
    except Exception as erreur:
        current_app.logger.exception("Impossible de charger la bibliothèque RAG: %s", erreur)
        return jsonify({"error": "rag_indisponible", "message": "La base documentaire est indisponible."}), 503


@bp.post("/documents")
@jwt_required()
def ajouter_document_route() -> ResponseReturnValue:
    """Extrait, découpe et indexe un PDF dans l'espace privé de l'utilisateur."""
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return jsonify({"error": "validation", "message": "Sélectionnez un fichier PDF."}), 400
    try:
        resultat = ajouter_pdf(fichier.read(), fichier.filename, str(get_jwt_identity()))
    except DocumentRAGError as erreur:
        return jsonify({"error": "validation", "message": str(erreur)}), 400
    except Exception as erreur:
        current_app.logger.exception("Échec de l'indexation PDF: %s", erreur)
        message = "L'indexation du PDF a échoué. Vérifiez les dépendances RAG et le modèle d'embeddings."
        if current_app.debug:
            message = f"{message} Détail : {erreur}"
        return jsonify({"error": "rag_indisponible", "message": message}), 503
    return jsonify(resultat), 201


@bp.delete("/documents/<string:document_id>")
@jwt_required()
def supprimer_document_route(document_id: str) -> ResponseReturnValue:
    """Supprime un PDF privé et ses vecteurs; les sources publiques sont protégées."""
    if not supprimer_pdf(document_id, str(get_jwt_identity())):
        return jsonify({"error": "not_found", "message": "Document introuvable."}), 404
    return jsonify({"supprime": True}), 200


@bp.get("/checklists")
def checklists_route() -> ResponseReturnValue:
    """Renvoie les checklists officielles de location (9 items) et vente (10 items).

    Returns:
        ResponseReturnValue: 200 avec les deux checklists détaillées.
    """
    transaction = request.args.get("transaction", "").lower()
    reponse: dict[str, Any] = {
        "location": {
            "total": len(CHECKLIST_LOCATION),
            "titre_fr": "Checklist — Documents pour une location immobilière",
            "titre_ar": "قائمة وثائق الكراء العقاري",
            "elements": CHECKLIST_LOCATION,
        },
        "vente": {
            "total": len(CHECKLIST_VENTE),
            "titre_fr": "Checklist — Documents pour une vente immobilière",
            "titre_ar": "قائمة وثائق البيع العقاري",
            "elements": CHECKLIST_VENTE,
        },
    }
    if transaction in ("location", "vente"):
        return jsonify({transaction: reponse[transaction]}), 200
    return jsonify(reponse), 200


@bp.get("/suggestions")
def suggestions_route() -> ResponseReturnValue:
    """Renvoie d'abord les questions extraites des PDF du compte, puis les exemples généraux.

    Returns:
        ResponseReturnValue: 200 avec les suggestions en français et en arabe.
    """
    langue = request.args.get("langue", "fr").lower()
    if langue not in ("fr", "ar"):
        langue = "fr"
    transaction = request.args.get("transaction", "general").lower()
    if transaction not in ("location", "vente"):
        transaction = "general"
    utilisateur = utilisateur_optionnel()
    try:
        personnalisees = suggestions_pdf(
            str(utilisateur.id) if utilisateur else None,
            langue=langue,
            transaction=transaction,
        )
    except Exception:
        current_app.logger.exception("Suggestions issues des PDF indisponibles")
        personnalisees = []
    generales = SUGGESTIONS_QUESTIONS[langue]
    if transaction in ("location", "vente"):
        generales = [s for s in generales if s["transaction"] in (transaction, "general")]
    return jsonify({"suggestions": (personnalisees + generales)[:8]}), 200


@bp.post("/analyser-document")
def analyser_document_route() -> ResponseReturnValue:
    """Analyse un contrat ou document PDF / texte et vérifie sa complétude.

    Returns:
        ResponseReturnValue: 200 avec diagnostic pagination, sauts, champs et checklist.
    """
    from app.ia.rag.analyseur_document import verifier_completude_contrat

    transaction = request.form.get("transaction") or request.args.get("transaction")
    langue = request.form.get("langue") or request.args.get("langue") or "fr"

    if "fichier" in request.files:
        fichier = request.files["fichier"]
        nom_fichier = fichier.filename or "document.pdf"
        contenu = fichier.read()
        if not contenu:
            return jsonify({"error": "validation", "message": "Le fichier envoyé est vide."}), 400
        rapport = verifier_completude_contrat(contenu, transaction_forcee=transaction, langue=langue)
        rapport["nom_fichier"] = nom_fichier
        return jsonify(rapport), 200

    donnees = request.get_json(silent=True) or {}
    texte = donnees.get("texte")
    if not texte:
        return jsonify({"error": "validation", "message": "Veuillez fournir un fichier PDF ou un texte à analyser."}), 400

    nom_fichier = donnees.get("nom_fichier") or "document.txt"
    rapport = verifier_completude_contrat(texte, transaction_forcee=donnees.get("transaction") or transaction, langue=donnees.get("langue") or langue)
    rapport["nom_fichier"] = nom_fichier
    return jsonify(rapport), 200


@bp.post("/generer-contrat")
def generer_contrat_route() -> ResponseReturnValue:
    """Génère un projet de contrat de bail ou promesse de vente conforme au droit tunisien.

    Returns:
        ResponseReturnValue: 200 avec le texte Markdown du contrat généré.
    """
    from app.ia.rag.generateur_contrat import generer_projet_bail, generer_projet_promesse_vente

    donnees = request.get_json() or {}
    type_contrat = donnees.get("type_contrat", "location").lower()
    langue = donnees.get("langue", "fr").lower()

    bailleur = donnees.get("bailleur") or donnees.get("vendeur") or {}
    locataire = donnees.get("locataire") or donnees.get("acheteur") or {}
    bien = donnees.get("bien") or {}
    conditions = donnees.get("conditions") or {}

    if type_contrat == "vente":
        texte_contrat = generer_projet_promesse_vente(bailleur, locataire, bien, conditions, langue=langue)
    else:
        texte_contrat = generer_projet_bail(bailleur, locataire, bien, conditions, langue=langue)

    return jsonify({
        "type_contrat": type_contrat,
        "langue": langue,
        "contrat_markdown": texte_contrat,
    }), 200
