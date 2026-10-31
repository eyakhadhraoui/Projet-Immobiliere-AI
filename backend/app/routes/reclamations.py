"""Routes de gestion des réclamations et signalements (préfixe ``/api/reclamations``)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import io
import json
from pathlib import Path
import uuid
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_file
from flask.typing import ResponseReturnValue
from sqlalchemy import or_, select
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Annonce,
    DecisionReclamation,
    PrioriteReclamation,
    Reclamation,
    ReclamationMessage,
    StatutAnnonce,
    StatutReclamation,
    TypeReclamation,
    Utilisateur,
)
from app.models.historique import ActionHistorique, AnnonceHistorique
from app.securite import utilisateur_optionnel
from app.services.assistant_reclamations import (
    AssistantReclamationError,
    ameliorer_description_reclamation,
    analyser_avec_gemini,
)

bp = Blueprint("reclamations", __name__, url_prefix="/api/reclamations")
TAILLE_PIECE_MAX = 5 * 1024 * 1024
MARGE_MULTIPART = 1024 * 1024


@bp.before_request
def autoriser_marge_multipart() -> None:
    """Ajoute une marge HTTP uniquement au formulaire avec fichiers."""
    if request.method == "POST" and request.endpoint == "reclamations.creer_reclamation":
        request.max_content_length = TAILLE_PIECE_MAX + MARGE_MULTIPART


def _valider_piece(fichier: Any) -> tuple[str, bytes] | None:
    """Vérifie le format réel et la taille d'une pièce jointe acceptée."""
    nom = secure_filename(fichier.filename or "")
    extension = Path(nom).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".pdf"}:
        return None
    contenu = fichier.read(TAILLE_PIECE_MAX + 1)
    if not contenu or len(contenu) > TAILLE_PIECE_MAX:
        return None
    if extension == ".pdf":
        valide = contenu.startswith(b"%PDF-")
    else:
        try:
            from PIL import Image
            image = Image.open(io.BytesIO(contenu))
            image.verify()
            valide = image.format == ("JPEG" if extension in {".jpg", ".jpeg"} else "PNG")
        except Exception:
            valide = False
    return (nom, contenu) if valide else None


@bp.post("/assistant/ameliorer-description")
def assistant_ameliorer_description() -> ResponseReturnValue:
    """Propose une reformulation Gemini sans modifier ni envoyer la réclamation."""
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        return jsonify(error="validation", message="Le corps JSON doit être un objet."), 400
    objet = donnees.get("objet", "")
    description = donnees.get("description", "")
    if not isinstance(objet, str) or not isinstance(description, str):
        return jsonify(error="validation", message="L'objet et la description doivent être du texte."), 400
    objet = objet.strip()
    description = description.strip()
    if not objet and not description:
        return jsonify(error="validation", message="Saisissez un objet ou quelques faits avant de demander une proposition."), 400
    if len(objet) > 150 or len(description) > 1000:
        return jsonify(error="validation", message="L'objet ne doit pas dépasser 150 caractères et la description 1 000 caractères."), 400
    try:
        proposition = ameliorer_description_reclamation(objet, description)
    except AssistantReclamationError as erreur:
        return jsonify(error="assistant_reclamation_indisponible", message=erreur.message), erreur.status
    return jsonify(
        description=proposition,
        mention="Proposition Gemini indicative : relisez et modifiez le texte avant de l'utiliser.",
    ), 200


@bp.post("/assistant/analyser")
def assistant_analyser_reclamation() -> ResponseReturnValue:
    """Analyse le texte avec Gemini, sans modifier la réclamation ni l'annonce."""
    donnees = request.get_json(silent=True) or {}
    objet = str(donnees.get("objet", ""))[:150]
    description = str(donnees.get("description", ""))[:1000]
    try:
        resultat = analyser_avec_gemini(objet, description)
    except AssistantReclamationError as erreur:
        return jsonify(error="assistant_reclamation_indisponible", message=erreur.message), erreur.status

    annonce_id = donnees.get("annonce_id")
    annonce = db.session.get(Annonce, annonce_id) if annonce_id else None
    if annonce:
        depuis = datetime.now() - timedelta(days=30)
        recentes = db.session.scalars(
            select(Reclamation).where(
                Reclamation.utilisateur_vise_id == annonce.owner_id,
                Reclamation.date_creation >= depuis,
                Reclamation.statut.in_([StatutReclamation.NOUVELLE, StatutReclamation.EN_COURS, StatutReclamation.EN_ATTENTE_INFO]),
            ).order_by(Reclamation.date_creation.desc()).limit(50)
        ).all()
        autres_annonces = {r.annonce_id for r in recentes if r.annonce_id and r.annonce_id != annonce.id}
        resultat["signalements_recents_meme_proprietaire"] = len(autres_annonces)
        resultat["annonces_similaires"] = [
            {"titre": r.annonce.titre if r.annonce else "Annonce signalée", "date": r.date_creation.date().isoformat()}
            for r in recentes if r.annonce_id in autres_annonces and r.annonce and r.annonce.statut == StatutAnnonce.PUBLIEE
        ][:3]
        motif = resultat["motif_suggere"]
        resultat["doublon_possible"] = any(
            r.annonce_id == annonce.id and r.type.value == motif for r in recentes
        )
    else:
        resultat["signalements_recents_meme_proprietaire"] = 0
        resultat["annonces_similaires"] = []
        resultat["doublon_possible"] = False
    return jsonify(resultat), 200


@bp.get("/<int:rec_id>/pieces-jointes/<string:nom_fichier>")
def telecharger_piece_reclamation(rec_id: int, nom_fichier: str) -> ResponseReturnValue:
    """Sert uniquement les pièces liées à cette réclamation."""
    rec = db.session.get(Reclamation, rec_id)
    if not rec:
        return jsonify({"error": "introuvable", "message": "Réclamation introuvable."}), 404
    piece = next((p for p in rec.pieces_jointes or [] if isinstance(p, dict) and p.get("fichier") == nom_fichier), None)
    if not piece or secure_filename(nom_fichier) != nom_fichier:
        return jsonify({"error": "introuvable", "message": "Pièce jointe introuvable."}), 404
    user = utilisateur_optionnel()
    if not user or (user.id != rec.user_id and user.id != rec.utilisateur_vise_id):
        return jsonify({"error": "interdit", "message": "Vous ne pouvez pas consulter cette pièce jointe."}), 403
    chemin = Path(current_app.config["UPLOAD_FOLDER"]) / "reclamations" / str(rec.id) / nom_fichier
    if not chemin.is_file():
        return jsonify({"error": "introuvable", "message": "Pièce jointe introuvable."}), 404
    return send_file(chemin, as_attachment=True, download_name=piece.get("nom", "piece"))


def _prochain_numero_reclamation() -> str:
    """Génère une référence unique type REC-2026-0001."""
    annee = date.today().year
    nb = db.session.scalar(select(db.func.count(Reclamation.id))) or 0
    return f"REC-{annee}-{nb + 1:04d}"


@bp.get("")
def lister_reclamations() -> ResponseReturnValue:
    """Liste les réclamations avec recherche textuelle et filtres."""
    recherche = request.args.get("recherche", "").strip()
    statut = request.args.get("statut", "").strip()
    type_r = request.args.get("type", "").strip()
    priorite = request.args.get("priorite", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 15))))

    requete = (
        select(Reclamation)
        .outerjoin(Annonce, Reclamation.annonce_id == Annonce.id)
        .outerjoin(Utilisateur, Reclamation.user_id == Utilisateur.id)
        .order_by(Reclamation.date_creation.desc())
    )

    if statut:
        requete = requete.where(Reclamation.statut == statut)
    if type_r:
        requete = requete.where(Reclamation.type == type_r)
    if priorite:
        requete = requete.where(Reclamation.priorite == priorite)
    if recherche:
        terme = f"%{recherche}%"
        requete = requete.where(
            or_(
                Reclamation.reference.ilike(terme),
                Reclamation.objet.ilike(terme),
                Reclamation.description.ilike(terme),
                Annonce.titre.ilike(terme),
                Utilisateur.nom.ilike(terme),
                Utilisateur.prenom.ilike(terme),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(requete.subquery())) or 0
    items_db = db.session.scalars(requete.offset((page - 1) * per_page).limit(per_page)).all()

    return jsonify({
        "items": [r.to_dict() for r in items_db],
        "total": total,
        "page": page,
        "per_page": per_page,
    }), 200


@bp.get("/<int:rec_id>")
def detail_reclamation(rec_id: int) -> ResponseReturnValue:
    """Renvoie le détail complet d'une réclamation avec ses messages."""
    rec = db.session.get(Reclamation, rec_id)
    if not rec:
        return jsonify({"error": "introuvable", "message": "Réclamation introuvable."}), 404
    return jsonify(rec.to_dict()), 200


@bp.post("")
def creer_reclamation() -> ResponseReturnValue:
    """Dépose une nouvelle réclamation avec contrôle anti-doublon, sans décision automatique."""
    fichiers: list[tuple[str, bytes]] = []
    if request.is_json:
        donnees = request.get_json() or {}
    else:
        try:
            donnees = json.loads(request.form.get("donnees", "{}"))
        except (TypeError, ValueError):
            return jsonify({"error": "validation", "message": "Les données du formulaire sont invalides."}), 400
        for fichier in request.files.getlist("pieces_jointes"):
            piece = _valider_piece(fichier)
            if piece is None:
                return jsonify({"error": "validation", "message": "Formats acceptés : JPG, PNG ou PDF; 5 Mo maximum par fichier."}), 400
            fichiers.append(piece)
    if sum(len(contenu) for _, contenu in fichiers) > TAILLE_PIECE_MAX:
        return jsonify({"error": "validation", "message": "La taille totale des pièces jointes ne peut pas dépasser 5 Mo."}), 400
    user = utilisateur_optionnel()
    user_id = donnees.get("user_id") or (user.id if user else 1)
    annonce_id = donnees.get("annonce_id")
    type_r = donnees.get("type", "fausse_annonce")

    # Règle 1 : Empêcher les doublons si même utilisateur + même annonce + même motif
    if annonce_id:
        doublon = db.session.scalars(
            select(Reclamation).where(
                Reclamation.user_id == user_id,
                Reclamation.annonce_id == annonce_id,
                Reclamation.type == type_r,
                Reclamation.statut.in_([
                    StatutReclamation.NOUVELLE,
                    StatutReclamation.EN_COURS,
                    StatutReclamation.EN_ATTENTE_INFO,
                ]),
            )
        ).first()
        if doublon:
            return jsonify({
                "error": "doublon",
                "message": f"Vous avez déjà déposé un signalement actif ({doublon.reference}) pour ce motif sur cette annonce.",
            }), 400

    annonce = db.session.get(Annonce, annonce_id) if annonce_id else None
    utilisateur_vise_id = donnees.get("utilisateur_vise_id") or (annonce.owner_id if annonce else None)

    rec = Reclamation(
        reference=_prochain_numero_reclamation(),
        user_id=user_id,
        annonce_id=annonce_id,
        utilisateur_vise_id=utilisateur_vise_id,
        type=TypeReclamation(type_r),
        objet=donnees.get("objet") or f"Signalement {type_r}",
        description=donnees.get("description") or "Détail du problème constaté.",
        statut=StatutReclamation.NOUVELLE,
        priorite=PrioriteReclamation(donnees.get("priorite", "normale")),
        pieces_jointes=donnees.get("pieces_jointes", []),
    )
    db.session.add(rec)
    db.session.flush()
    pieces_sauvees: list[Path] = []
    if fichiers:
        repertoire = Path(current_app.config["UPLOAD_FOLDER"]) / "reclamations" / str(rec.id)
        repertoire.mkdir(parents=True, exist_ok=True)
        for nom_original, contenu in fichiers:
            extension = Path(nom_original).suffix.lower()
            nom_stocke = f"{uuid.uuid4().hex}{extension}"
            chemin = repertoire / nom_stocke
            chemin.write_bytes(contenu)
            pieces_sauvees.append(chemin)
            rec.pieces_jointes.append({"nom": nom_original, "fichier": nom_stocke})

    # Règle 4 : Enregistrer l'action dans l'historique
    if annonce:
        historique = AnnonceHistorique(
            annonce_id=annonce.id,
            titre_annonce=annonce.titre,
            action=ActionHistorique.MODIFICATION,
            details={"type": "reclamation_deposee", "reference": rec.reference, "motif": rec.type.value},
            owner_id=annonce.owner_id,
        )
        db.session.add(historique)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        for chemin in pieces_sauvees:
            chemin.unlink(missing_ok=True)
        raise
    return jsonify(rec.to_dict()), 201


@bp.put("/<int:rec_id>")
def modifier_reclamation(rec_id: int) -> ResponseReturnValue:
    """Traite une réclamation (statut, réponse admin, décision et sanctions)."""
    rec = db.session.get(Reclamation, rec_id)
    if not rec:
        return jsonify({"error": "introuvable", "message": "Réclamation introuvable."}), 404

    donnees = request.get_json() or {}
    user = utilisateur_optionnel()

    if "statut" in donnees:
        rec.statut = StatutReclamation(donnees["statut"])
        if rec.statut in (StatutReclamation.RESOLUE, StatutReclamation.CLOTUREE, StatutReclamation.REJETEE):
            rec.date_cloture = datetime.now()
        elif rec.statut == StatutReclamation.EN_COURS and not rec.date_traitement:
            rec.date_traitement = datetime.now()

    if "priorite" in donnees:
        rec.priorite = PrioriteReclamation(donnees["priorite"])
    if "reponse_admin" in donnees:
        rec.reponse_admin = donnees["reponse_admin"]
        rec.traite_par = user.id if user else 1
    if "decision" in donnees and donnees["decision"]:
        rec.decision = DecisionReclamation(donnees["decision"])

        # Appliquer la décision sur l'annonce si applicable
        if rec.annonce:
            if rec.decision == DecisionReclamation.ANNONCE_SUSPENDUE:
                rec.annonce.statut = StatutAnnonce.BROUILLON
            elif rec.decision == DecisionReclamation.ANNONCE_SUPPRIMEE:
                rec.annonce.statut = StatutAnnonce.ARCHIVEE

    db.session.commit()
    return jsonify(rec.to_dict()), 200


@bp.post("/<int:rec_id>/messages")
def ajouter_message_reclamation(rec_id: int) -> ResponseReturnValue:
    """Ajoute un message dans le fil de discussion de la réclamation."""
    rec = db.session.get(Reclamation, rec_id)
    if not rec:
        return jsonify({"error": "introuvable", "message": "Réclamation introuvable."}), 404

    donnees = request.get_json() or {}
    message_texte = donnees.get("message", "").strip()
    if not message_texte:
        return jsonify({"error": "validation", "message": "Le texte du message est requis."}), 400

    user = utilisateur_optionnel()
    auteur_id = donnees.get("auteur_id") or (user.id if user else 1)

    msg = ReclamationMessage(
        reclamation_id=rec.id,
        auteur_id=auteur_id,
        message=message_texte,
    )
    db.session.add(msg)

    # Si la réclamation était nouvelle, elle passe automatiquement en cours
    if rec.statut == StatutReclamation.NOUVELLE:
        rec.statut = StatutReclamation.EN_COURS
        rec.date_traitement = datetime.now()

    db.session.commit()
    return jsonify(rec.to_dict()), 201


@bp.delete("/<int:rec_id>")
def supprimer_reclamation(rec_id: int) -> ResponseReturnValue:
    """Supprime une réclamation après confirmation."""
    rec = db.session.get(Reclamation, rec_id)
    if not rec:
        return jsonify({"error": "introuvable", "message": "Réclamation introuvable."}), 404

    ref = rec.reference
    db.session.delete(rec)
    db.session.commit()

    return jsonify({"message": f"Réclamation {ref} supprimée avec succès."}), 200
