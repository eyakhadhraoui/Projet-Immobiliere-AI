"""API privée d'organisation locale des preuves de litiges locatifs."""

from __future__ import annotations

import csv
import html
import io
import json
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_file
from flask.typing import ResponseReturnValue
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError as SchemaValidationError
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app import db
from app.ia.litiges.analyse import (
    ROLES_AUTEUR, classifier, embedding_local, extraire_dates, modele_semantique_disponible, repondre, rechercher,
)
from app.ia.litiges.documents import decouper_passages, extraire_document
from app.ia.organisateur_litige import dossier_dir, extraire_pdf, rapport_dossier
from app.models import (
    AnnotationLitige, CitationLitige, ClassificationLitige, DateLitige, DocumentLitige,
    DossierLitige, PassageLitige, QuestionLitige, RapportLitige,
)
from app.schemas.dossiers_litige_schema import (
    DossierLitigeCreationSchema, QuestionLitigeSchema, RapportLitigeSchema,
)
from app.services.dossier_litige_service import repondre_question
from app.services.location_service import contexte_litige_location, location_pour_participant

bp = Blueprint("dossiers_litige", __name__, url_prefix="/api/dossiers-litige")
ID_RE = re.compile(r"^[0-9a-f]{32}$")
AVERTISSEMENT = (
    "Outil d'organisation et de recherche documentaire. Il ne fournit pas de conseil juridique, "
    "ne détermine pas qui a raison et ne prédit pas l'issue d'une procédure. Les pièces ne sont pas authentifiées."
)


def _user_id() -> int:
    return int(get_jwt_identity())


def _dossier(case_id: str) -> DossierLitige | None:
    if not ID_RE.fullmatch(case_id):
        return None
    return db.session.scalar(select(DossierLitige).where(
        DossierLitige.case_id == case_id, DossierLitige.proprietaire_id == _user_id()
    ))


def _legacy_path(user_id: str, case_id: str) -> Path | None:
    if not ID_RE.fullmatch(case_id):
        return None
    return dossier_dir(current_app.config["DOSSIERS_LITIGE_FOLDER"], user_id) / f"{case_id}.json"


def _legacy_load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _as_iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def _case_dict(case: DossierLitige, include_text: bool = True) -> dict[str, Any]:
    docs = []
    for doc in case.documents:
        chunks = []
        for chunk in doc.passages:
            classification = chunk.classification
            chunks.append({
                "id": chunk.chunk_id, "chunk_id": chunk.chunk_id, "texte": chunk.texte if include_text else "",
                "source": doc.nom_fichier, "page": chunk.page,
                "types": [classification.type_preuve] if classification else ["other"],
                "sujets": [classification.sujet] if classification else ["other"],
                "auteur_attribue": doc.role_auteur if doc.role_auteur in {"tenant", "landlord"} else None,
                "role_auteur": doc.role_auteur,
                "dates": [_as_iso(d.date_normalisee) for d in chunk.dates],
                "debut": chunk.debut, "fin": chunk.fin,
                "needs_review": classification.revue_humaine if classification else True,
                "score": classification.score if classification else 0.0,
            })
        docs.append({
            "id": doc.id, "nom": doc.nom_fichier, "titre": doc.titre, "auteur": doc.auteur,
            "role_auteur": doc.role_auteur, "date_document": _as_iso(doc.date_document),
            "type_mime": doc.type_mime, "cree_le": _as_iso(doc.cree_le), "hash_fichier": doc.hash_fichier,
            "passages": chunks,
        })
    return {
        "id": case.case_id, "case_id": case.case_id, "nom": case.titre, "titre": case.titre,
        "description": case.description, "langue": case.langue, "juridiction": case.juridiction,
        "provenance": case.provenance, "cree_le": _as_iso(case.cree_le),
        "modifie_le": _as_iso(case.modifie_le),
        "location": contexte_litige_location(case.location), "documents": docs,
    }


def _case_list_item(case: DossierLitige) -> dict[str, Any]:
    return {"id": case.case_id, "case_id": case.case_id, "nom": case.titre, "titre": case.titre,
            "description": case.description, "langue": case.langue, "juridiction": case.juridiction,
            "cree_le": _as_iso(case.cree_le), "location": contexte_litige_location(case.location),
            "documents": [{"id": d.id, "nom": d.nom_fichier,
            "titre": d.titre, "role_auteur": d.role_auteur, "passages": []} for d in case.documents]}


def _tous_passages(case: DossierLitige) -> list[dict[str, Any]]:
    items = []
    for document in case.documents:
        for chunk in document.passages:
            classification = chunk.classification
            items.append({
                "chunk_id": chunk.chunk_id, "texte": chunk.texte, "page": chunk.page,
                "document_id": document.id, "nom_fichier": document.nom_fichier, "titre": document.titre,
                "auteur": document.auteur, "role_auteur": document.role_auteur,
                "type_preuve": classification.type_preuve if classification else "other",
                "sujet": classification.sujet if classification else "other",
                "score_classification": classification.score if classification else 0.0,
                "needs_review": classification.revue_humaine if classification else True,
                "debut": chunk.debut, "fin": chunk.fin, "embedding": chunk.embedding,
            })
    return items


@bp.get("")
@jwt_required()
def lister() -> ResponseReturnValue:
    cases = db.session.scalars(select(DossierLitige).where(
        DossierLitige.proprietaire_id == _user_id()
    ).order_by(DossierLitige.modifie_le.desc())).all()
    items = [_case_list_item(case) for case in cases]
    # Old JSON dossiers remain readable; their files are not migrated or deleted.
    racine = dossier_dir(current_app.config["DOSSIERS_LITIGE_FOLDER"], str(_user_id()))
    for path in racine.glob("*.json"):
        legacy = _legacy_load(path)
        if legacy and not any(item["id"] == legacy.get("id") for item in items):
            legacy["legacy"] = True
            items.append(legacy)
    return jsonify({"dossiers": items}), 200


@bp.post("")
@jwt_required()
def creer() -> ResponseReturnValue:
    donnees = request.get_json(silent=True) or {}
    if "titre" not in donnees and "nom" in donnees:
        donnees = {**donnees, "titre": donnees["nom"]}
        donnees.pop("nom", None)
    try:
        valide = DossierLitigeCreationSchema().load(donnees)
    except SchemaValidationError as erreur:
        return jsonify(error="validation", message="Données du dossier invalides.", details=erreur.messages), 400
    titre = valide["titre"].strip()
    description = valide["description"].strip()
    langue = valide["langue"]
    juridiction = (valide["juridiction"] or "").strip() or None
    provenance = (valide["provenance"] or "").strip() or None
    location = None
    if valide.get("location_id") is not None:
        location = location_pour_participant(valide["location_id"], _user_id())
        if location is None:
            return jsonify(error="not_found", message="Contrat de location introuvable."), 404
    if not titre:
        return jsonify(error="validation", message="Le titre ne peut pas être vide."), 400
    case = DossierLitige(case_id=uuid.uuid4().hex, proprietaire_id=_user_id(), titre=titre,
                         location=location, description=description, langue=langue,
                         juridiction=juridiction, provenance=provenance)
    db.session.add(case)
    db.session.commit()
    return jsonify(_case_dict(case)), 201


@bp.get("/configuration")
@jwt_required()
def configuration() -> ResponseReturnValue:
    return jsonify({"legal_warning": AVERTISSEMENT, "local_only": True,
                    "formats": ["PDF", "DOCX", "TXT", "Markdown", "EML", "JSON"],
                    "max_file_bytes": 4 * 1024 * 1024,
                    "semantic_model_available": modele_semantique_disponible(current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE")),
                    "limits": ["Les documents sont des pièces non vérifiées.",
                               "Les dates extraites ne sont pas authentifiées.",
                               "L'absence de résultat ne prouve pas l'absence d'une preuve.",
                               "Aucun document privé n'est envoyé à un service externe."]}), 200


@bp.get("/<string:case_id>")
@jwt_required()
def detail(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if case:
        return jsonify(_case_dict(case)), 200
    legacy = _legacy_load(_legacy_path(str(_user_id()), case_id)) if _legacy_path(str(_user_id()), case_id) else None
    return (jsonify(legacy), 200) if legacy else (jsonify(error="not_found", message="Dossier introuvable."), 404)


@bp.patch("/<string:case_id>")
@jwt_required()
def modifier_dossier(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    donnees = request.get_json(silent=True) or {}
    autorises = {"titre", "description", "langue", "juridiction", "provenance"}
    if set(donnees) - autorises:
        return jsonify(error="validation", message="Champ de dossier non autorisé."), 400
    try:
        valide = DossierLitigeCreationSchema().load({
            "titre": donnees.get("titre", case.titre),
            "description": donnees.get("description", case.description),
            "langue": donnees.get("langue", case.langue),
            "juridiction": donnees.get("juridiction", case.juridiction),
            "provenance": donnees.get("provenance", case.provenance),
        })
    except SchemaValidationError as erreur:
        return jsonify(error="validation", message="Données du dossier invalides.", details=erreur.messages), 400
    for name, value in valide.items():
        setattr(case, name, value.strip() if isinstance(value, str) and name not in {"langue"} else value)
    case.modifie_le = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_case_dict(case)), 200


@bp.delete("/<string:case_id>")
@jwt_required()
def supprimer(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if case:
        dossier_fichiers = _racine_stockage(str(_user_id()), case_id)
        db.session.delete(case)
        db.session.commit()
        if dossier_fichiers.exists():
            shutil.rmtree(dossier_fichiers)
        return jsonify(message="Dossier et documents supprimés."), 200
    legacy_path = _legacy_path(str(_user_id()), case_id)
    legacy = _legacy_load(legacy_path) if legacy_path else None
    if not legacy or not legacy_path:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    legacy_path.unlink(missing_ok=True)
    return jsonify(message="Ancien dossier supprimé."), 200


@bp.post("/<string:case_id>/documents")
@jwt_required()
def ajouter_document(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        legacy_path = _legacy_path(str(_user_id()), case_id)
        legacy = _legacy_load(legacy_path) if legacy_path else None
        fichier = request.files.get("fichier")
        if legacy and fichier and Path(fichier.filename or "").suffix.lower() == ".pdf":
            # Compatibility path for older JSON dossiers. New uploads use relational storage below.
            nom = secure_filename(fichier.filename)
            try:
                passages = extraire_pdf(fichier.read(), nom)
            except ValueError as erreur:
                return jsonify(error="validation", message=str(erreur)), 400
            legacy.setdefault("documents", []).append({"id": uuid.uuid4().hex, "nom": nom, "passages": passages})
            _legacy_path_write(legacy, legacy_path)
            return jsonify(document={"id": legacy["documents"][-1]["id"], "nom": nom,
                                     "passages": len(passages)}), 201
        return jsonify(error="not_found", message="Dossier introuvable ou ancien dossier en lecture seule."), 404
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return jsonify(error="validation", message="Sélectionnez un document."), 400
    nom = secure_filename(Path(fichier.filename).name)[:255]
    if not nom:
        return jsonify(error="validation", message="Nom de fichier invalide."), 400
    contenu = fichier.read(4 * 1024 * 1024 + 1)
    try:
        texte, mime, pages, digest = extraire_document(contenu, nom)
    except ValueError as erreur:
        return jsonify(error="validation", message=str(erreur)), 400
    if db.session.scalar(select(DocumentLitige.id).where(
        DocumentLitige.case_id == case_id, DocumentLitige.hash_fichier == digest
    )):
        return jsonify(error="duplicate_document", message="Ce fichier est déjà présent dans ce dossier."), 409

    role = str(request.form.get("role_auteur", "unknown")).strip().lower()
    auteur = str(request.form.get("auteur", "")).strip() or None
    titre = str(request.form.get("titre", Path(nom).stem)).strip() or Path(nom).stem
    raw_date = str(request.form.get("date_document", "")).strip()
    date_document = None
    if role not in ROLES_AUTEUR or len(titre) > 255 or (auteur and len(auteur) > 160):
        return jsonify(error="validation", message="Métadonnées invalides."), 400
    if raw_date:
        try:
            date_document = date.fromisoformat(raw_date)
        except ValueError:
            return jsonify(error="validation", message="La date du document doit être au format AAAA-MM-JJ."), 400

    suffixe = Path(nom).suffix.lower()
    nom_stocke = f"{uuid.uuid4().hex}{suffixe}"
    chemin = _racine_stockage(str(_user_id()), case_id) / nom_stocke
    chemin.parent.mkdir(parents=True, exist_ok=True)
    try:
        chemin.write_bytes(contenu)
        document = DocumentLitige(case_id=case_id, nom_fichier=nom, nom_stocke=nom_stocke, titre=titre,
                                  auteur=auteur, role_auteur=role, date_document=date_document,
                                  texte_extrait=texte, hash_fichier=digest, type_mime=mime)
        db.session.add(document)
        db.session.flush()
        for item in decouper_passages(texte, pages):
            chunk_id = uuid.uuid4().hex
            raw = str(item["texte"])
            passage = PassageLitige(case_id=case_id, document_id=document.id, chunk_id=chunk_id, texte=raw,
                                    debut=int(item["debut"]), fin=int(item["fin"]), page=item["page"],
                                    embedding=embedding_local(raw, current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE")),
                                    retrieval_metadata={"title": titre, "author_role": role, "source": nom})
            db.session.add(passage)
            type_preuve, sujet, score = classifier(raw)
            db.session.add(ClassificationLitige(chunk_id=chunk_id, type_preuve=type_preuve, sujet=sujet,
                                                score=score, revue_humaine=True, verifie_manuellement=False))
            for date_item in extraire_dates(raw, role):
                db.session.add(DateLitige(chunk_id=chunk_id, date_normalisee=date_item["date"],
                                          texte_source=date_item["source_text"], attribution=role, verifiee=False))
        case.modifie_le = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        chemin.unlink(missing_ok=True)
        raise
    return jsonify(document={"id": document.id, "nom": document.nom_fichier, "titre": document.titre,
                             "role_auteur": document.role_auteur, "type_mime": document.type_mime,
                             "passages": len(document.passages), "hash_fichier": document.hash_fichier}), 201


@bp.get("/<string:case_id>/documents")
@jwt_required()
def lister_documents(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    return jsonify(items=[{"id": d.id, "filename": d.nom_fichier, "title": d.titre, "author": d.auteur,
                          "author_role": d.role_auteur, "document_date": _as_iso(d.date_document),
                          "mime_type": d.type_mime,
                          "created_at": _as_iso(d.cree_le), "chunk_count": len(d.passages),
                          "download_url": f"/api/dossiers-litige/{case_id}/documents/{d.id}/fichier"}
                         for d in case.documents]), 200


@bp.get("/<string:case_id>/documents/<int:document_id>")
@jwt_required()
def detail_document(case_id: str, document_id: int) -> ResponseReturnValue:
    doc = _document_proprietaire(case_id, document_id)
    if not doc:
        return jsonify(error="not_found", message="Document introuvable."), 404
    return jsonify(_document_dict(doc)), 200


@bp.patch("/<string:case_id>/documents/<int:document_id>")
@jwt_required()
def modifier_metadonnees_document(case_id: str, document_id: int) -> ResponseReturnValue:
    doc = _document_proprietaire(case_id, document_id)
    if not doc:
        return jsonify(error="not_found", message="Document introuvable."), 404
    donnees = request.get_json(silent=True) or {}
    autorises = {"title", "author", "author_role", "document_date"}
    if set(donnees) - autorises:
        return jsonify(error="validation", message="Champ de document non autorisé."), 400
    titre = str(donnees.get("title", doc.titre)).strip()
    auteur = str(donnees.get("author", doc.auteur or "")).strip() or None
    role = str(donnees.get("author_role", doc.role_auteur)).strip().lower()
    date_value = donnees.get("document_date", _as_iso(doc.date_document))
    try:
        document_date = date.fromisoformat(date_value) if date_value else None
    except (TypeError, ValueError):
        return jsonify(error="validation", message="Date du document invalide (AAAA-MM-JJ)."), 400
    if not titre or len(titre) > 255 or (auteur and len(auteur) > 160) or role not in ROLES_AUTEUR:
        return jsonify(error="validation", message="Métadonnées invalides."), 400
    doc.titre, doc.auteur, doc.role_auteur, doc.date_document = titre, auteur, role, document_date
    for chunk in doc.passages:
        chunk.retrieval_metadata = {**(chunk.retrieval_metadata or {}), "title": titre, "author_role": role}
        for extracted in chunk.dates:
            extracted.attribution = role
    db.session.commit()
    return jsonify(_document_dict(doc)), 200


@bp.get("/<string:case_id>/documents/<int:document_id>/fichier")
@jwt_required()
def telecharger_document(case_id: str, document_id: int) -> ResponseReturnValue:
    doc = _document_proprietaire(case_id, document_id)
    if not doc:
        return jsonify(error="not_found", message="Document introuvable."), 404
    chemin = _racine_stockage(str(_user_id()), case_id) / doc.nom_stocke
    if not chemin.is_file():
        return jsonify(error="not_found", message="Fichier original indisponible."), 404
    return send_file(chemin, as_attachment=True, download_name=doc.nom_fichier, mimetype=doc.type_mime,
                     max_age=0, conditional=True)


@bp.delete("/<string:case_id>/documents/<int:document_id>")
@jwt_required()
def supprimer_document(case_id: str, document_id: int) -> ResponseReturnValue:
    doc = _document_proprietaire(case_id, document_id)
    if not doc:
        return jsonify(error="not_found", message="Document introuvable."), 404
    chemin = _racine_stockage(str(_user_id()), case_id) / doc.nom_stocke
    db.session.delete(doc)
    db.session.commit()
    chemin.unlink(missing_ok=True)
    return jsonify(message="Document et passages supprimés."), 200


@bp.post("/<string:case_id>/process")
@jwt_required()
def traiter(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    passages = _tous_passages(case)
    return jsonify(status="processed", documents=len(case.documents), passages=len(passages),
                   dates=sum(len(p.dates) for d in case.documents for p in d.passages),
                   classification="règles locales; revue humaine requise",
                   retrieval="hybride local" if modele_semantique_disponible(current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE")) else "TF-IDF local",
                   legal_warning=AVERTISSEMENT), 200


@bp.get("/<string:case_id>/evidence")
@jwt_required()
def preuves(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    auteur = request.args.get("author_role", "").strip()
    nom_auteur = request.args.get("author", "").strip().casefold()
    type_preuve = request.args.get("evidence_type", "").strip()
    date_min = request.args.get("date_from", "").strip()
    date_max = request.args.get("date_to", "").strip()
    try:
        dmin = date.fromisoformat(date_min) if date_min else None
        dmax = date.fromisoformat(date_max) if date_max else None
    except ValueError:
        return jsonify(error="validation", message="Les filtres de date doivent être au format AAAA-MM-JJ."), 400
    raw_confidence = request.args.get("confidence_min", "").strip()
    try:
        confidence_min = float(raw_confidence) if raw_confidence else None
    except ValueError:
        return jsonify(error="validation", message="Le seuil de confiance doit être un nombre entre 0 et 1."), 400
    if (dmin and dmax and dmin > dmax) or (confidence_min is not None and not 0 <= confidence_min <= 1):
        return jsonify(error="validation", message="Filtres invalides."), 400
    items = []
    for passage in _tous_passages(case):
        if auteur and passage["role_auteur"] != auteur:
            continue
        if nom_auteur and nom_auteur not in str(passage["auteur"] or "").casefold():
            continue
        if type_preuve and passage["type_preuve"] != type_preuve:
            continue
        if confidence_min is not None and passage["score_classification"] < confidence_min:
            continue
        passage_dates = [d.date_normalisee for doc in case.documents for p in doc.passages
                         if p.chunk_id == passage["chunk_id"] for d in p.dates]
        if dmin and (not passage_dates or max(passage_dates) < dmin):
            continue
        if dmax and (not passage_dates or min(passage_dates) > dmax):
            continue
        items.append(passage)
    return jsonify(items=items, total=len(items), verification_humaine_requise=True), 200


@bp.get("/<string:case_id>/timeline")
@jwt_required()
def chronologie(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    items = []
    for doc in case.documents:
        for chunk in doc.passages:
            for extracted in chunk.dates:
                items.append({"date": extracted.date_normalisee.isoformat(), "event": extracted.texte_source,
                              "source": doc.nom_fichier, "title": doc.titre, "author": doc.auteur,
                              "author_role": doc.role_auteur, "chunk_id": chunk.chunk_id,
                              "quote": extracted.texte_source, "confidence": 1.0,
                              "verified": False, "status": "date extraite du document, non vérifiée"})
    items.sort(key=lambda item: item["date"])
    return jsonify(items=items, legal_warning=AVERTISSEMENT), 200


@bp.get("/<string:case_id>/accounts")
@jwt_required()
def comptes_parties(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    result: dict[str, list[dict[str, Any]]] = {"tenant": [], "landlord": []}
    for item in _tous_passages(case):
        role = item["role_auteur"]
        if role in result and item["type_preuve"] == "party_statement":
            result[role].append({"text": item["texte"], "source": item["nom_fichier"],
                                 "author": item["auteur"], "chunk_id": item["chunk_id"],
                                 "issue": item["sujet"], "status": "déclaration non authentifiée"})
    return jsonify(items=result), 200


@bp.get("/<string:case_id>/contradictions")
@jwt_required()
def contradictions(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    roles: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in _tous_passages(case):
        if item["type_preuve"] == "party_statement" and item["role_auteur"] in {"tenant", "landlord"}:
            roles.setdefault(item["sujet"], {"tenant": [], "landlord": []})[item["role_auteur"]].append(item)
    candidates = []
    for issue, groups in roles.items():
        for tenant in groups["tenant"]:
            for landlord in groups["landlord"]:
                candidates.append({"issue": issue, "status": "à vérifier humainement",
                                   "tenant": {"quote": tenant["texte"], "source": tenant["nom_fichier"], "chunk_id": tenant["chunk_id"]},
                                   "landlord": {"quote": landlord["texte"], "source": landlord["nom_fichier"], "chunk_id": landlord["chunk_id"]}})
    return jsonify(items=candidates, note="Des déclarations sur un même sujet ne sont pas automatiquement une contradiction établie."), 200


@bp.get("/<string:case_id>/missing-evidence")
@jwt_required()
def preuves_non_retrouvees(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    present = {item["type_preuve"] for item in _tous_passages(case)}
    all_types = {"payment_record", "lease_clause", "condition_report", "repair_record", "notice", "party_statement", "correspondence"}
    return jsonify(items=[{"evidence_type": kind, "status": "aucun passage identifié dans les documents importés"}
                          for kind in sorted(all_types - present)],
                   warning="Un type de pièce non retrouvé dans ce dossier ne signifie pas qu'il n'existe pas."), 200


@bp.post("/<string:case_id>/search")
@jwt_required()
def recherche(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    donnees = request.get_json(silent=True) or {}
    try:
        question = QuestionLitigeSchema().load(donnees)["question"].strip()
    except SchemaValidationError as erreur:
        return jsonify(error="validation", message="Question invalide.", details=erreur.messages), 400
    if not question:
        return jsonify(error="validation", message="La question ne peut pas être vide."), 400
    result = rechercher(question, _tous_passages(case), current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE"))
    return jsonify({**result, "legal_warning": AVERTISSEMENT}), 200


@bp.post("/<string:case_id>/questions")
@jwt_required()
def question(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    donnees = request.get_json(silent=True) or {}
    try:
        question_text = QuestionLitigeSchema().load(donnees)["question"].strip()
    except SchemaValidationError as erreur:
        return jsonify(error="validation", message="Question invalide.", details=erreur.messages), 400
    if not question_text:
        return jsonify(error="validation", message="La question ne peut pas être vide."), 400
    result = repondre_question(
        case, question_text, current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE")
    )
    return jsonify({**result, "legal_warning": AVERTISSEMENT}), 200


@bp.patch("/<string:case_id>/classifications/<string:chunk_id>")
@jwt_required()
def corriger_classification(case_id: str, chunk_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    donnees = request.get_json(silent=True) or {}
    type_preuve = str(donnees.get("evidence_type", "")).strip()
    sujet = str(donnees.get("issue", "other")).strip()
    known_types = {"payment_record", "lease_clause", "condition_report", "repair_record", "notice", "party_statement", "correspondence", "other"}
    known_issues = {"deposit", "rent_arrears", "repairs", "notice", "utilities", "access", "other"}
    chunk = db.session.scalar(select(PassageLitige).where(PassageLitige.case_id == case_id,
                                                          PassageLitige.chunk_id == chunk_id))
    if not chunk:
        return jsonify(error="not_found", message="Passage introuvable."), 404
    if type_preuve not in known_types or sujet not in known_issues:
        return jsonify(error="validation", message="Type de preuve ou sujet invalide."), 400
    classification = chunk.classification or ClassificationLitige(chunk_id=chunk_id)
    classification.type_preuve, classification.sujet = type_preuve, sujet
    classification.score, classification.revue_humaine, classification.verifie_manuellement = 1.0, False, True
    db.session.add(classification)
    db.session.commit()
    return jsonify(message="Classification corrigée manuellement.", evidence_type=type_preuve, issue=sujet,
                   needs_review=False), 200


@bp.post("/<string:case_id>/annotations")
@jwt_required()
def annoter(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    data = request.get_json(silent=True) or {}
    chunk_id = str(data.get("chunk_id", ""))
    label, value = str(data.get("label", "")).strip(), str(data.get("value", "")).strip()
    chunk = db.session.scalar(select(PassageLitige).where(PassageLitige.case_id == case_id,
                                                          PassageLitige.chunk_id == chunk_id))
    if not chunk:
        return jsonify(error="not_found", message="Passage introuvable."), 404
    if not label or len(label) > 80 or not value or len(value) > 5000:
        return jsonify(error="validation", message="L'étiquette et le texte de l'annotation sont requis."), 400
    annotation = AnnotationLitige(chunk_id=chunk_id, auteur_id=_user_id(), etiquette=label, valeur=value)
    db.session.add(annotation)
    db.session.commit()
    return jsonify(id=annotation.id, chunk_id=chunk_id, label=label, value=value,
                   status="annotation humaine, non vérifiée"), 201


@bp.post("/<string:case_id>/reports")
@jwt_required()
def creer_rapport(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case:
        return jsonify(error="not_found", message="Dossier introuvable."), 404
    data = request.get_json(silent=True) or {}
    try:
        format_ = RapportLitigeSchema().load(data)["format"].lower()
    except SchemaValidationError as erreur:
        return jsonify(error="validation", message="Format de rapport invalide.", details=erreur.messages), 400
    report = _rapport_payload(case)
    contenu = _rendre_rapport(report, format_)
    identifiant = uuid.uuid4().hex
    row = RapportLitige(report_id=identifiant, case_id=case_id, format=format_, contenu=contenu)
    db.session.add(row)
    db.session.commit()
    return jsonify(report_id=identifiant, format=format_, download_url=f"/api/dossiers-litige/{case_id}/reports/{identifiant}",
                   created_at=_as_iso(row.cree_le), legal_warning=AVERTISSEMENT), 201


@bp.get("/<string:case_id>/reports/<string:report_id>")
@jwt_required()
def obtenir_rapport(case_id: str, report_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if not case or not ID_RE.fullmatch(report_id):
        return jsonify(error="not_found", message="Rapport introuvable."), 404
    report = db.session.scalar(select(RapportLitige).where(RapportLitige.case_id == case_id,
                                                            RapportLitige.report_id == report_id))
    if not report:
        return jsonify(error="not_found", message="Rapport introuvable."), 404
    mime = {"json": "application/json", "markdown": "text/markdown", "html": "text/html", "csv": "text/csv"}[report.format]
    return current_app.response_class(report.contenu, mimetype=mime, headers={
        "Content-Disposition": f"attachment; filename=rapport-litige-{case_id}.{_extension_rapport(report.format)}",
        "X-Content-Type-Options": "nosniff",
    }), 200


@bp.get("/<string:case_id>/rapport")
@jwt_required()
def rapport_compat(case_id: str) -> ResponseReturnValue:
    case = _dossier(case_id)
    if case:
        question_text = request.args.get("question", "").strip()
        payload = _rapport_payload(case)
        if question_text:
            payload["answer"] = repondre(question_text, _tous_passages(case), current_app.config.get("DOSSIERS_LITIGE_MODELE_SEMANTIQUE"))
        return jsonify(payload), 200
    legacy_path = _legacy_path(str(_user_id()), case_id)
    legacy = _legacy_load(legacy_path) if legacy_path else None
    if legacy:
        return jsonify(rapport_dossier(legacy.get("nom", "Dossier"), legacy.get("documents", []), request.args.get("question", "")[:500])), 200
    return jsonify(error="not_found", message="Dossier introuvable."), 404


def _document_proprietaire(case_id: str, document_id: int) -> DocumentLitige | None:
    if not _dossier(case_id):
        return None
    return db.session.scalar(select(DocumentLitige).where(DocumentLitige.case_id == case_id,
                                                           DocumentLitige.id == document_id))


def _document_dict(doc: DocumentLitige) -> dict[str, Any]:
    return {"id": doc.id, "filename": doc.nom_fichier, "title": doc.titre, "author": doc.auteur,
            "author_role": doc.role_auteur, "document_date": _as_iso(doc.date_document), "mime_type": doc.type_mime,
            "file_hash": doc.hash_fichier, "created_at": _as_iso(doc.cree_le), "text": doc.texte_extrait,
            "chunks": [{"chunk_id": c.chunk_id, "text": c.texte, "start_offset": c.debut,
                        "end_offset": c.fin, "page": c.page} for c in doc.passages]}


def _racine_stockage(user_id: str, case_id: str) -> Path:
    base = Path(current_app.config["DOSSIERS_LITIGE_FOLDER"]).resolve()
    chemin = (base / "documents" / user_id / case_id).resolve()
    if base not in chemin.parents:
        raise ValueError("Chemin de stockage invalide.")
    return chemin


def _legacy_path_write(dossier: dict[str, Any], chemin: Path) -> None:
    temporaire = chemin.with_suffix(".tmp")
    temporaire.write_text(json.dumps(dossier, ensure_ascii=False), encoding="utf-8")
    temporaire.replace(chemin)


def _rapport_payload(case: DossierLitige) -> dict[str, Any]:
    passages = _tous_passages(case)
    timeline = []
    party_accounts = {"tenant": [], "landlord": []}
    for doc in case.documents:
        for chunk in doc.passages:
            for date_item in chunk.dates:
                timeline.append({"date": date_item.date_normalisee.isoformat(), "event": date_item.texte_source,
                                 "source": doc.nom_fichier, "author": doc.auteur, "author_role": doc.role_auteur,
                                 "quote": date_item.texte_source, "verified": False})
            if doc.role_auteur in party_accounts and chunk.classification and chunk.classification.type_preuve == "party_statement":
                party_accounts[doc.role_auteur].append({"quote": chunk.texte, "source": doc.nom_fichier,
                                                          "chunk_id": chunk.chunk_id, "status": "déclaration non authentifiée"})
    timeline.sort(key=lambda item: item["date"])
    types_present = sorted({p["type_preuve"] for p in passages})
    return {
        "case": {"case_id": case.case_id, "title": case.titre, "description": case.description,
                 "language": case.langue, "jurisdiction": case.juridiction, "created_at": _as_iso(case.cree_le)},
        "legal_warning": AVERTISSEMENT,
        "documents": [{"id": d.id, "filename": d.nom_fichier, "title": d.titre, "author": d.auteur,
                       "author_role": d.role_auteur, "document_date": _as_iso(d.date_document),
                       "sha256": d.hash_fichier, "mime_type": d.type_mime, "chunks": len(d.passages)} for d in case.documents],
        "evidence_inventory": {"recognized_types": types_present, "passage_count": len(passages),
                               "all_classifications_need_human_review": True},
        "timeline": timeline, "party_accounts": party_accounts,
        "retrieved_passages": [{"chunk_id": p["chunk_id"], "source": p["nom_fichier"], "quote": p["texte"],
                                "type": p["type_preuve"], "issue": p["sujet"]} for p in passages],
        "potential_contradictions": _contradictions_payload(passages),
        "evidence_not_identified": sorted({"payment_record", "lease_clause", "condition_report", "repair_record",
                                            "notice", "party_statement", "correspondence"} - set(types_present)),
        "human_review_questions": ["Les pièces et leurs auteurs sont-ils authentiques ?",
                                   "Les dates extraites correspondent-elles aux événements décrits ?",
                                   "Les déclarations de chaque partie sont-elles étayées par des pièces indépendantes ?"],
        "limitations": ["Les classements et dates sont indicatifs et demandent une vérification humaine.",
                        "Une déclaration de partie n'est pas un fait établi.",
                        "Une preuve de paiement n'établit pas automatiquement un remboursement.",
                        "Un passage non retrouvé ne prouve pas l'absence d'une pièce."],
    }


def _contradictions_payload(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in passages:
        if item["type_preuve"] == "party_statement" and item["role_auteur"] in {"tenant", "landlord"}:
            groups.setdefault(item["sujet"], {"tenant": [], "landlord": []})[item["role_auteur"]].append(item)
    return [{"issue": issue, "status": "à vérifier humainement",
             "tenant_quote": tenant["texte"], "tenant_source": tenant["nom_fichier"],
             "landlord_quote": landlord["texte"], "landlord_source": landlord["nom_fichier"]}
            for issue, pair in groups.items() for tenant in pair["tenant"] for landlord in pair["landlord"]]


def _rendre_rapport(data: dict[str, Any], format_: str) -> str:
    if format_ == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if format_ == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["date", "event", "source", "author", "author_role", "quote", "verified"])
        writer.writeheader()
        writer.writerows(data["timeline"])
        return output.getvalue()
    case = data["case"]
    lines = [f"# {case['title']}", "", f"> {AVERTISSEMENT}", "", "## Documents importés"]
    lines.extend(f"- {d['filename']} — rôle déclaré : {d['author_role']} — passages : {d['chunks']}" for d in data["documents"])
    lines.extend(["", "## Chronologie"])
    lines.extend(f"- {x['date']} — {x['quote']} ({x['source']}; non vérifié)" for x in data["timeline"])
    lines.extend(["", "## Déclarations du locataire", *[f"- {x['quote']} ({x['source']}; non authentifiée)" for x in data["party_accounts"]["tenant"]]])
    lines.extend(["", "## Déclarations du propriétaire", *[f"- {x['quote']} ({x['source']}; non authentifiée)" for x in data["party_accounts"]["landlord"]]])
    lines.extend(["", "## Contradictions potentielles à vérifier humainement"])
    lines.extend(f"- Sujet {x['issue']} : locataire « {x['tenant_quote']} » ; propriétaire « {x['landlord_quote']} »" for x in data["potential_contradictions"])
    lines.extend(["", "## Passages retrouvés"])
    lines.extend(f"- [{x['source']} · {x['chunk_id']}] {x['quote']}" for x in data["retrieved_passages"])
    lines.extend(["", "## Éléments non identifiés dans les documents importés", *[f"- {x}" for x in data["evidence_not_identified"]],
                  "", "## Limites", *[f"- {x}" for x in data["limitations"]]])
    markdown = "\n".join(lines)
    if format_ == "markdown":
        return markdown
    return "<!doctype html><html lang='fr'><meta charset='utf-8'><title>Rapport du dossier</title>" \
           "<body><main><h1>Rapport du dossier locatif</h1><p><strong>" + html.escape(AVERTISSEMENT) + "</strong></p><pre>" + \
           html.escape(markdown) + "</pre></main></body></html>"


def _extension_rapport(format_: str) -> str:
    return {"json": "json", "markdown": "md", "html": "html", "csv": "csv"}[format_]
