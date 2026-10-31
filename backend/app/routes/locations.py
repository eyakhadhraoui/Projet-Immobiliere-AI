"""Routes de gestion des locations et baux immobiliers (préfixe ``/api/locations``)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy import or_, select

from app import db
from app.models import (
    Annonce,
    EtatDesLieux,
    LocationImmo,
    Loyer,
    PeriodiciteLocation,
    StatutLocation,
    StatutLoyer,
    TypeLocation,
    Utilisateur,
)
from app.models.historique import ActionHistorique, AnnonceHistorique
from app.securite import utilisateur_optionnel

bp = Blueprint("locations", __name__, url_prefix="/api/locations")


def _prochain_numero_location() -> str:
    """Génère une référence unique type LOC-2026-0001."""
    annee = date.today().year
    nb = db.session.scalar(select(db.func.count(LocationImmo.id))) or 0
    return f"LOC-{annee}-{nb + 1:04d}"


@bp.get("")
def lister_locations() -> ResponseReturnValue:
    """Liste les contrats de location avec recherche textuelle et filtres."""
    recherche = request.args.get("recherche", "").strip()
    statut = request.args.get("statut", "").strip()
    type_loc = request.args.get("type_location", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 15))))

    requete = (
        select(LocationImmo)
        .outerjoin(Annonce, LocationImmo.annonce_id == Annonce.id)
        .outerjoin(Utilisateur, LocationImmo.locataire_id == Utilisateur.id)
        .order_by(LocationImmo.date_creation.desc())
    )

    if statut:
        requete = requete.where(LocationImmo.statut == statut)
    if type_loc:
        requete = requete.where(LocationImmo.type_location == type_loc)
    if recherche:
        terme = f"%{recherche}%"
        requete = requete.where(
            or_(
                LocationImmo.reference.ilike(terme),
                Annonce.titre.ilike(terme),
                Annonce.ville.ilike(terme),
                Utilisateur.nom.ilike(terme),
                Utilisateur.prenom.ilike(terme),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(requete.subquery())) or 0
    items_db = db.session.scalars(requete.offset((page - 1) * per_page).limit(per_page)).all()

    return jsonify({
        "items": [loc.to_dict() for loc in items_db],
        "total": total,
        "page": page,
        "per_page": per_page,
    }), 200


@bp.get("/<int:loc_id>")
def detail_location(loc_id: int) -> ResponseReturnValue:
    """Renvoie le détail d'un contrat de location."""
    loc = db.session.get(LocationImmo, loc_id)
    if not loc:
        return jsonify({"error": "introuvable", "message": "Contrat de location introuvable."}), 404
    return jsonify(loc.to_dict()), 200


@bp.post("")
def creer_location() -> ResponseReturnValue:
    """Crée un contrat de bail et initialise son échéancier mensuel."""
    donnees = request.get_json() or {}
    annonce_id = donnees.get("annonce_id")
    if not annonce_id:
        premiere = db.session.scalars(select(Annonce).limit(1)).first()
        if premiere:
            annonce_id = premiere.id

    annonce = db.session.get(Annonce, annonce_id) if annonce_id else None
    if not annonce:
        return jsonify({"error": "validation", "message": "Veuillez associer une annonce existante."}), 400

    user = utilisateur_optionnel()
    proprietaire_id = annonce.owner_id or 1
    locataire_id = donnees.get("locataire_id") or (user.id if user else 1)

    today = date.today()
    date_deb = today
    if donnees.get("date_debut"):
        try:
            date_deb = date.fromisoformat(str(donnees["date_debut"]).split("T")[0])
        except Exception:
            pass

    duree_mois = int(donnees.get("duree_mois", 12))
    # Date fin approximative (date début + 30 * duree_mois)
    date_fin = date_deb + timedelta(days=duree_mois * 30)
    if donnees.get("date_fin"):
        try:
            date_fin = date.fromisoformat(str(donnees["date_fin"]).split("T")[0])
        except Exception:
            pass

    loyer_mensuel = Decimal(str(donnees.get("loyer_mensuel") or annonce.prix or 900))
    charges = Decimal(str(donnees.get("charges") or 0))
    caution = Decimal(str(donnees.get("caution") or (loyer_mensuel * Decimal(2))))

    loc = LocationImmo(
        reference=_prochain_numero_location(),
        annonce_id=annonce.id,
        proprietaire_id=proprietaire_id,
        locataire_id=locataire_id,
        transaction_id=donnees.get("transaction_id"),
        type_location=TypeLocation(donnees.get("type_location", "longue_duree")),
        date_debut=date_deb,
        date_fin=date_fin,
        duree_mois=duree_mois,
        loyer_mensuel=loyer_mensuel,
        charges=charges,
        caution=caution,
        jour_paiement=int(donnees.get("jour_paiement", 5)),
        periodicite=PeriodiciteLocation(donnees.get("periodicite", "mensuel")),
        statut=StatutLocation(donnees.get("statut", "active")),
        preavis_jours=int(donnees.get("preavis_jours", 90)),
        renouvellement_auto=bool(donnees.get("renouvellement_auto", True)),
    )
    db.session.add(loc)
    db.session.flush()

    # Générer les échéances mensuelles initiales (au moins 6 mois)
    for i in range(min(12, duree_mois)):
        # Calculer le mois d'échéance
        annee = date_deb.year + (date_deb.month + i - 1) // 12
        mois = (date_deb.month + i - 1) % 12 + 1
        jour = min(loc.jour_paiement, 28)
        echeance = date(annee, mois, jour)

        statut_l = StatutLoyer.A_PAYER
        # Le mois courant ou premier mois peut être marqué payé si déjà encaissé
        if i == 0 and donnees.get("premier_loyer_paye"):
            statut_l = StatutLoyer.PAYE

        loyer = Loyer(
            location_id=loc.id,
            periode=date(annee, mois, 1),
            montant_du=loyer_mensuel + charges,
            montant_paye=(loyer_mensuel + charges) if statut_l == StatutLoyer.PAYE else Decimal(0),
            date_echeance=echeance,
            date_paiement=date.today() if statut_l == StatutLoyer.PAYE else None,
            statut=statut_l,
        )
        db.session.add(loyer)

    historique = AnnonceHistorique(
        annonce_id=annonce.id,
        titre_annonce=annonce.titre,
        action=ActionHistorique.MODIFICATION,
        details={"type": "location_creee", "reference": loc.reference, "loyer": float(loyer_mensuel)},
        owner_id=proprietaire_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify(loc.to_dict()), 201


@bp.put("/<int:loc_id>")
def modifier_location(loc_id: int) -> ResponseReturnValue:
    """Met à jour un contrat de location."""
    loc = db.session.get(LocationImmo, loc_id)
    if not loc:
        return jsonify({"error": "introuvable", "message": "Contrat de location introuvable."}), 404

    donnees = request.get_json() or {}
    if "statut" in donnees:
        loc.statut = StatutLocation(donnees["statut"])
    if "type_location" in donnees:
        loc.type_location = TypeLocation(donnees["type_location"])
    if "loyer_mensuel" in donnees:
        loc.loyer_mensuel = Decimal(str(donnees["loyer_mensuel"]))
    if "charges" in donnees:
        loc.charges = Decimal(str(donnees["charges"]))
    if "caution" in donnees:
        loc.caution = Decimal(str(donnees["caution"]))
    if "jour_paiement" in donnees:
        loc.jour_paiement = int(donnees["jour_paiement"])
    if "preavis_jours" in donnees:
        loc.preavis_jours = int(donnees["preavis_jours"])
    if "motif_resiliation" in donnees:
        loc.motif_resiliation = donnees["motif_resiliation"]
    if "contrat_pdf" in donnees:
        loc.contrat_pdf = donnees["contrat_pdf"]

    db.session.commit()
    return jsonify(loc.to_dict()), 200


@bp.delete("/<int:loc_id>")
def supprimer_location(loc_id: int) -> ResponseReturnValue:
    """Supprime un contrat de location après confirmation."""
    loc = db.session.get(LocationImmo, loc_id)
    if not loc:
        return jsonify({"error": "introuvable", "message": "Contrat de location introuvable."}), 404

    ref = loc.reference
    annonce_id = loc.annonce_id
    titre_annonce = loc.annonce.titre if loc.annonce else "Annonce"
    owner_id = loc.proprietaire_id

    db.session.delete(loc)
    historique = AnnonceHistorique(
        annonce_id=annonce_id,
        titre_annonce=titre_annonce,
        action=ActionHistorique.SUPPRESSION,
        details={"type": "location_supprimee", "reference": ref},
        owner_id=owner_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify({"message": f"Contrat de location {ref} supprimé avec succès."}), 200


@bp.post("/<int:loc_id>/loyers/<int:loyer_id>/encaisser")
def encaisser_loyer(loc_id: int, loyer_id: int) -> ResponseReturnValue:
    """Marque une échéance de loyer comme réglée/encaissée."""
    loyer = db.session.get(Loyer, loyer_id)
    if not loyer or loyer.location_id != loc_id:
        return jsonify({"error": "introuvable", "message": "Échéance de loyer introuvable."}), 404

    loyer.statut = StatutLoyer.PAYE
    loyer.montant_paye = loyer.montant_du
    loyer.date_paiement = date.today()
    loyer.quittance_pdf = f"quittance_{loc_id}_{loyer_id}.pdf"

    db.session.commit()
    return jsonify(loyer.to_dict()), 200
