"""Signalements de maintenance pour les baux actifs, interventions, notifications et historique."""

from __future__ import annotations

import json
from pathlib import Path
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import or_, select

from app import db
from app.models import (CategorieMaintenance, DemandeMaintenance, EvenementMaintenance,
                        LocationImmo, NotificationMaintenance, PrioriteMaintenance,
                        RoleUtilisateur, StatutLocation, StatutMaintenance)
from app.services.photo_service import controler_image, enregistrer_fichier

bp = Blueprint("maintenance", __name__, url_prefix="/api/maintenance")
MAX_PHOTOS = 5


def _nom(user) -> str:
    return f"{user.prenom} {user.nom}".strip()


def _evenement(demande, action: str, detail: str) -> None:
    db.session.add(EvenementMaintenance(demande_id=demande.id, auteur_id=current_user.id, action=action, detail=detail))


def _notifier(user_id: int, demande, message: str) -> None:
    if user_id == current_user.id:
        return
    db.session.add(NotificationMaintenance(utilisateur_id=user_id, demande_id=demande.id, message=message))


def _visible():
    req = select(DemandeMaintenance)
    if current_user.role == RoleUtilisateur.PROPRIETAIRE:
        return req.where(or_(DemandeMaintenance.proprietaire_id == current_user.id,
                             DemandeMaintenance.locataire_id == current_user.id))
    return req.where(DemandeMaintenance.locataire_id == current_user.id)


def _obtenir(demande_id: int):
    demande = db.session.scalar(_visible().where(DemandeMaintenance.id == demande_id))
    return demande


@bp.get("/locations-actives")
@jwt_required()
def locations_actives() -> ResponseReturnValue:
    if current_user.role == RoleUtilisateur.CLIENT:
        condition = LocationImmo.locataire_id == current_user.id
    elif current_user.role == RoleUtilisateur.PROPRIETAIRE:
        condition = or_(LocationImmo.proprietaire_id == current_user.id, LocationImmo.locataire_id == current_user.id)
    else:
        return jsonify(message="Rôle non autorisé."), 403
    locations = db.session.scalars(select(LocationImmo).where(
        condition, LocationImmo.statut == StatutLocation.ACTIVE
    ).order_by(LocationImmo.date_debut.desc())).all()
    return jsonify(items=[{"id": loc.id, "reference": loc.reference,
                          "titre": loc.annonce.titre if loc.annonce else "Bien immobilier",
                          "ville": loc.annonce.ville if loc.annonce else "",
                          "loyer_mensuel": float(loc.loyer_mensuel),
                          "proprietaire_nom": _nom(loc.proprietaire)} for loc in locations]), 200


@bp.get("")
@jwt_required()
def lister_demandes() -> ResponseReturnValue:
    statut = request.args.get("statut", "").strip()
    priorite = request.args.get("priorite", "").strip()
    categorie = request.args.get("categorie", "").strip()
    recherche = request.args.get("recherche", "").strip()
    location_id = request.args.get("location_id", type=int)
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(50, max(1, request.args.get("per_page", 30, type=int)))
    base = _visible()
    toutes = db.session.scalars(base).all()
    total = len(toutes)
    query = base
    if location_id:
        query = query.where(DemandeMaintenance.location_id == location_id)
    if statut:
        query = query.where(DemandeMaintenance.statut == statut)
    if priorite:
        query = query.where(DemandeMaintenance.priorite == priorite)
    if categorie:
        query = query.where(DemandeMaintenance.categorie == categorie)
    if recherche:
        term = f"%{recherche}%"
        query = query.where(or_(DemandeMaintenance.reference.ilike(term), DemandeMaintenance.titre.ilike(term), DemandeMaintenance.description.ilike(term)))
    total_filtre = db.session.scalar(select(db.func.count()).select_from(query.subquery())) or 0
    records = db.session.scalars(query.order_by(DemandeMaintenance.date_creation.desc()).offset((page - 1) * per_page).limit(per_page)).all()
    stats = {s.value: sum(1 for x in toutes if x.statut == s) for s in StatutMaintenance}
    mois = datetime.now().strftime("%Y-%m")
    stats["cout_reel"] = sum(float(x.cout_reel or 0) for x in toutes if x.statut == StatutMaintenance.CLOTUREE and x.date_maj.strftime("%Y-%m") == mois)
    return jsonify(items=[x.to_dict() for x in records], total=total_filtre, total_global=total, page=page, per_page=per_page, stats=stats), 200


@bp.post("")
@jwt_required()
def creer_demande() -> ResponseReturnValue:
    if current_user.role not in {RoleUtilisateur.CLIENT, RoleUtilisateur.PROPRIETAIRE}:
        return jsonify(message="Compte non autorisé à signaler un problème."), 403
    try:
        donnees = json.loads(request.form.get("donnees", "{}"))
    except (TypeError, json.JSONDecodeError):
        return jsonify(message="Données du formulaire invalides."), 400
    location = db.session.get(LocationImmo, donnees.get("location_id"))
    participe_au_bail = location and current_user.id in {location.locataire_id, location.proprietaire_id}
    if not location or not participe_au_bail or location.statut != StatutLocation.ACTIVE:
        return jsonify(message="Choisissez un contrat actif auquel votre compte est associé."), 400
    try:
        categorie = CategorieMaintenance(donnees.get("categorie", ""))
        priorite = PrioriteMaintenance(donnees.get("priorite", "normale"))
    except ValueError:
        return jsonify(message="Catégorie ou priorité invalide."), 400
    titre, description = str(donnees.get("titre", "")).strip(), str(donnees.get("description", "")).strip()
    piece = str(donnees.get("piece", "autre")).strip()
    if piece not in {"cuisine", "salle_de_bain", "salon", "chambre", "toilettes", "autre"}:
        return jsonify(message="Pièce invalide."), 400
    if not titre or len(titre) > 160 or not description or len(description) > 5000:
        return jsonify(message="Le titre et une description (max. 5 000 caractères) sont obligatoires."), 400
    fichiers = [f for f in request.files.getlist("photos") if f.filename]
    if len(fichiers) > MAX_PHOTOS:
        return jsonify(message=f"Vous pouvez joindre au maximum {MAX_PHOTOS} photos."), 400
    validations = [controler_image(f) for f in fichiers]
    if any(not ext for ext, _ in validations):
        return jsonify(message=next(err for ext, err in validations if not ext)), 400
    demande = DemandeMaintenance(
        reference=f"MNT-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}", location_id=location.id,
        locataire_id=location.locataire_id, proprietaire_id=location.proprietaire_id,
        categorie=categorie, piece=piece, titre=titre, description=description, priorite=priorite,
    )
    db.session.add(demande)
    db.session.flush()
    dossier_prive = Path(current_app.config["UPLOAD_FOLDER"]) / "maintenance" / str(demande.id)
    dossier_prive.mkdir(parents=True, exist_ok=True)
    urls = []
    for fichier, (extension, _) in zip(fichiers, validations):
        chemin, _url_public = enregistrer_fichier(fichier, extension)
        destination = dossier_prive / chemin.name
        chemin.replace(destination)
        urls.append(f"/api/maintenance/{demande.id}/photos/{destination.name}")
    demande.photos = urls
    _evenement(demande, "signalee", f"Signalée par {_nom(current_user)}")
    _notifier(location.proprietaire_id, demande, f"Nouveau signalement {priorite.value} : {titre}")
    db.session.commit()
    return jsonify(demande.to_dict()), 201


@bp.get("/notifications")
@jwt_required()
def notifications() -> ResponseReturnValue:
    items = db.session.scalars(select(NotificationMaintenance).where(
        NotificationMaintenance.utilisateur_id == current_user.id
    ).order_by(NotificationMaintenance.date_creation.desc()).limit(50)).all()
    return jsonify(items=[x.to_dict() for x in items], non_lues=sum(not x.lue for x in items)), 200


@bp.patch("/notifications/<int:notification_id>/lue")
@jwt_required()
def marquer_notification_lue(notification_id: int) -> ResponseReturnValue:
    item = db.session.scalar(select(NotificationMaintenance).where(
        NotificationMaintenance.id == notification_id, NotificationMaintenance.utilisateur_id == current_user.id
    ))
    if not item:
        return jsonify(message="Notification introuvable."), 404
    item.lue = True
    db.session.commit()
    return jsonify(item.to_dict()), 200


@bp.get("/<int:demande_id>")
@jwt_required()
def detail(demande_id: int) -> ResponseReturnValue:
    demande = _obtenir(demande_id)
    return (jsonify(demande.to_dict()), 200) if demande else (jsonify(message="Demande introuvable."), 404)


@bp.get("/<int:demande_id>/photos/<filename>")
@jwt_required()
def photo(demande_id: int, filename: str) -> ResponseReturnValue:
    """Sert une photo uniquement au locataire et au propriétaire de la demande."""
    demande = _obtenir(demande_id)
    if not demande or f"/api/maintenance/{demande_id}/photos/{filename}" not in (demande.photos or []):
        return jsonify(message="Photo introuvable."), 404
    dossier = Path(current_app.config["UPLOAD_FOLDER"]) / "maintenance" / str(demande_id)
    response = send_from_directory(dossier, filename)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.patch("/<int:demande_id>")
@jwt_required()
def modifier(demande_id: int) -> ResponseReturnValue:
    if current_user.role != RoleUtilisateur.PROPRIETAIRE:
        return jsonify(message="Action réservée au propriétaire du bien."), 403
    demande = _obtenir(demande_id)
    if not demande:
        return jsonify(message="Demande introuvable."), 404
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    notifications_locataire = {
        "accepter": (StatutMaintenance.SIGNALEE, StatutMaintenance.ACCEPTEE, "Votre demande de maintenance a été acceptée."),
        "refuser": (StatutMaintenance.SIGNALEE, StatutMaintenance.REFUSEE, "Votre demande de maintenance a été refusée."),
        "assigner": (StatutMaintenance.ACCEPTEE, StatutMaintenance.ASSIGNEE, "Un technicien a été assigné à votre demande."),
        "planifier": (StatutMaintenance.ASSIGNEE, StatutMaintenance.PLANIFIEE, "L'intervention de maintenance a été planifiée."),
        "cloturer": (StatutMaintenance.PLANIFIEE, StatutMaintenance.CLOTUREE, "L'intervention de maintenance est clôturée."),
    }
    if action not in notifications_locataire:
        return jsonify(message="Action invalide."), 400
    statut_attendu, statut_final, message = notifications_locataire[action]
    if demande.statut != statut_attendu:
        return jsonify(message=f"Action impossible pour le statut « {demande.statut.value} »."), 409
    detail_action = message
    try:
        if action == "assigner":
            nom = str(data.get("technicien_nom", "")).strip()
            if not nom:
                raise ValueError("Le nom du technicien est obligatoire.")
            demande.technicien_nom = nom[:160]
            demande.technicien_telephone = str(data.get("technicien_telephone", "")).strip()[:30] or None
            detail_action = f"Technicien assigné : {nom}"
        elif action == "planifier":
            moment = datetime.fromisoformat(str(data.get("date_intervention", "")).replace("Z", "+00:00"))
            estimation = Decimal(str(data.get("cout_estime") or "0"))
            if estimation < 0:
                raise ValueError("Le coût estimé ne peut pas être négatif.")
            demande.date_intervention = moment
            demande.cout_estime = estimation
            detail_action = f"Intervention planifiée le {moment.isoformat()}"
        elif action == "cloturer":
            cout = Decimal(str(data.get("cout_reel", "")))
            if cout < 0:
                raise ValueError("Le coût réel ne peut pas être négatif.")
            demande.cout_reel = cout
            demande.note_cloture = str(data.get("note_cloture", "")).strip()[:2000] or None
            detail_action = f"Intervention clôturée · coût réel : {cout} TND"
        elif action == "refuser":
            motif = str(data.get("motif", "")).strip()[:500]
            if motif:
                detail_action = f"Demande refusée : {motif}"
    except (ValueError, InvalidOperation, TypeError) as error:
        return jsonify(message=str(error) or "Vérifiez les données de l'intervention."), 400
    demande.statut = statut_final
    _evenement(demande, action, detail_action)
    _notifier(demande.locataire_id, demande, message)
    db.session.commit()
    return jsonify(demande.to_dict()), 200
