"""Routes de gestion et d'administration des utilisateurs (préfixe ``/api/utilisateurs``)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy import or_, select

from app import db
from app.models import RoleUtilisateur, Utilisateur
from app.services.utilisateur_service import creer_compte, normaliser_email

bp = Blueprint("utilisateurs", __name__, url_prefix="/api/utilisateurs")


@bp.get("")
def lister_utilisateurs() -> ResponseReturnValue:
    """Liste tous les utilisateurs avec recherche textuelle et filtres."""
    recherche = request.args.get("recherche", "").strip()
    role = request.args.get("role", "").strip()
    cin_verifiee = request.args.get("cin_verifiee")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 15))))

    requete = select(Utilisateur).order_by(Utilisateur.created_at.desc())

    if role:
        requete = requete.where(Utilisateur.role == role)
    if cin_verifiee is not None and cin_verifiee != "":
        est_verifiee = cin_verifiee.lower() in ("true", "1")
        requete = requete.where(Utilisateur.cin_verifiee == est_verifiee)

    if recherche:
        terme = f"%{recherche}%"
        requete = requete.where(
            or_(
                Utilisateur.nom.ilike(terme),
                Utilisateur.prenom.ilike(terme),
                Utilisateur.email.ilike(terme),
                Utilisateur.telephone.ilike(terme),
                Utilisateur.ville.ilike(terme),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(requete.subquery())) or 0
    items_db = db.session.scalars(requete.offset((page - 1) * per_page).limit(per_page)).all()

    return jsonify({
        "items": [u.to_dict() for u in items_db],
        "total": total,
        "page": page,
        "per_page": per_page,
    }), 200


@bp.get("/<int:user_id>")
def detail_utilisateur(user_id: int) -> ResponseReturnValue:
    """Renvoie la fiche détaillée d'un utilisateur avec ses annonces."""
    user = db.session.get(Utilisateur, user_id)
    if not user:
        return jsonify({"error": "introuvable", "message": "Utilisateur introuvable."}), 404

    donnees = user.to_dict()
    donnees["annonces"] = [
        {"id": a.id, "titre": a.titre, "ville": a.ville, "prix": float(a.prix), "statut": a.statut.value}
        for a in (user.annonces or [])
    ]
    return jsonify(donnees), 200


@bp.post("")
def creer_utilisateur() -> ResponseReturnValue:
    """Crée un nouvel utilisateur (espace administration)."""
    donnees = request.get_json() or {}

    email = normaliser_email(donnees.get("email", ""))
    if not email:
        return jsonify({"error": "validation", "message": "L'adresse email est requise."}), 400

    existant = db.session.scalar(select(Utilisateur.id).where(Utilisateur.email == email))
    if existant:
        return jsonify({"error": "conflit", "message": "Un compte existe déjà avec cette adresse email."}), 409

    mot_de_passe = donnees.get("mot_de_passe") or "Password123!"
    role = RoleUtilisateur(donnees.get("role", "client"))

    utilisateur = creer_compte({
        "nom": donnees.get("nom", "Nom"),
        "prenom": donnees.get("prenom", "Prénom"),
        "email": email,
        "mot_de_passe": mot_de_passe,
        "role": role,
        "telephone": donnees.get("telephone"),
        "ville": donnees.get("ville", "Tunis"),
        "adresse": donnees.get("adresse"),
    })

    return jsonify(utilisateur.to_dict()), 201


@bp.put("/<int:user_id>")
def modifier_utilisateur(user_id: int) -> ResponseReturnValue:
    """Met à jour les informations ou les droits d'un compte."""
    user = db.session.get(Utilisateur, user_id)
    if not user:
        return jsonify({"error": "introuvable", "message": "Utilisateur introuvable."}), 404

    donnees = request.get_json() or {}

    if "nom" in donnees:
        user.nom = donnees["nom"].strip()
    if "prenom" in donnees:
        user.prenom = donnees["prenom"].strip()
    if "telephone" in donnees:
        user.telephone = donnees["telephone"].strip() if donnees["telephone"] else None
    if "ville" in donnees:
        user.ville = donnees["ville"].strip() if donnees["ville"] else None
    if "adresse" in donnees:
        user.adresse = donnees["adresse"].strip() if donnees["adresse"] else None
    if "role" in donnees:
        user.role = RoleUtilisateur(donnees["role"])
    if "cin_verifiee" in donnees:
        user.cin_verifiee = bool(donnees["cin_verifiee"])
    if "visage_verifie" in donnees:
        user.visage_verifie = bool(donnees["visage_verifie"])

    if "mot_de_passe" in donnees and donnees["mot_de_passe"]:
        user.definir_mot_de_passe(donnees["mot_de_passe"])
        user.jeton_version += 1

    db.session.commit()
    return jsonify(user.to_dict()), 200


@bp.delete("/<int:user_id>")
def supprimer_utilisateur(user_id: int) -> ResponseReturnValue:
    """Supprime un compte utilisateur après confirmation."""
    user = db.session.get(Utilisateur, user_id)
    if not user:
        return jsonify({"error": "introuvable", "message": "Utilisateur introuvable."}), 404

    nom_complet = f"{user.prenom} {user.nom}"
    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": f"Compte de {nom_complet} supprimé avec succès."}), 200
