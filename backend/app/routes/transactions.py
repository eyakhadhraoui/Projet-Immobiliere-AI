"""Routes de gestion des transactions et paiements (préfixe ``/api/transactions``)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy import or_, select

from app import db
from app.models import (
    Annonce,
    ModePaiement,
    Paiement,
    StatutPaiement,
    StatutTransaction,
    TransactionImmo,
    TypeTransaction,
    Utilisateur,
)
from app.models.historique import ActionHistorique, AnnonceHistorique
from app.securite import utilisateur_optionnel

bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")


def _prochain_numero_transaction() -> str:
    """Génère une référence unique type TRX-2026-0001."""
    annee = date.today().year
    nb = db.session.scalar(select(db.func.count(TransactionImmo.id))) or 0
    return f"TRX-{annee}-{nb + 1:04d}"


@bp.get("")
def lister_transactions() -> ResponseReturnValue:
    """Liste les transactions avec recherche textuelle et filtres."""
    recherche = request.args.get("recherche", "").strip()
    statut = request.args.get("statut", "").strip()
    type_t = request.args.get("type_transaction", "").strip()
    mode_p = request.args.get("mode_paiement", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 15))))

    requete = (
        select(TransactionImmo)
        .outerjoin(Annonce, TransactionImmo.annonce_id == Annonce.id)
        .outerjoin(Utilisateur, TransactionImmo.acheteur_id == Utilisateur.id)
        .order_by(TransactionImmo.date_transaction.desc())
    )

    if statut:
        requete = requete.where(TransactionImmo.statut == statut)
    if type_t:
        requete = requete.where(TransactionImmo.type_transaction == type_t)
    if mode_p:
        requete = requete.where(TransactionImmo.mode_paiement == mode_p)
    if recherche:
        terme = f"%{recherche}%"
        requete = requete.where(
            or_(
                TransactionImmo.reference.ilike(terme),
                TransactionImmo.notaire.ilike(terme),
                TransactionImmo.reference_acte.ilike(terme),
                Annonce.titre.ilike(terme),
                Utilisateur.nom.ilike(terme),
                Utilisateur.prenom.ilike(terme),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(requete.subquery())) or 0
    items_db = db.session.scalars(requete.offset((page - 1) * per_page).limit(per_page)).all()

    return jsonify({
        "items": [t.to_dict() for t in items_db],
        "total": total,
        "page": page,
        "per_page": per_page,
    }), 200


@bp.get("/<int:trans_id>")
def detail_transaction(trans_id: int) -> ResponseReturnValue:
    """Renvoie le détail complet d'une transaction."""
    t = db.session.get(TransactionImmo, trans_id)
    if not t:
        return jsonify({"error": "introuvable", "message": "Transaction introuvable."}), 404
    return jsonify(t.to_dict()), 200


@bp.post("")
def creer_transaction() -> ResponseReturnValue:
    """Crée une nouvelle transaction immobilière."""
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
    vendeur_id = annonce.owner_id or 1
    acheteur_id = donnees.get("acheteur_id") or (user.id if user else 1)

    montant_total = Decimal(str(donnees.get("montant_total") or annonce.prix or 100000))
    acompte = Decimal(str(donnees.get("acompte") or 0))
    reste_a_payer = montant_total - acompte
    commission = Decimal(str(donnees.get("commission_plateforme") or (montant_total * Decimal("0.02"))))

    date_sig = None
    if donnees.get("date_signature"):
        try:
            date_sig = date.fromisoformat(str(donnees["date_signature"]).split("T")[0])
        except Exception:
            pass

    trans = TransactionImmo(
        reference=_prochain_numero_transaction(),
        annonce_id=annonce.id,
        type_transaction=TypeTransaction(donnees.get("type_transaction", "vente")),
        vendeur_id=vendeur_id,
        acheteur_id=acheteur_id,
        montant_total=montant_total,
        acompte=acompte,
        reste_a_payer=reste_a_payer,
        commission_plateforme=commission,
        mode_paiement=ModePaiement(donnees.get("mode_paiement", "virement")),
        statut=StatutTransaction(donnees.get("statut", "en_cours")),
        date_signature=date_sig,
        notaire=donnees.get("notaire"),
        reference_acte=donnees.get("reference_acte"),
        observations=donnees.get("observations"),
    )
    db.session.add(trans)
    db.session.flush()

    # Si acompte versé immédiatement, enregistrer le premier paiement
    if acompte > 0:
        paiement = Paiement(
            transaction_id=trans.id,
            montant=acompte,
            mode_paiement=trans.mode_paiement,
            reference_paiement=f"PAI-{trans.reference}-01",
            statut=StatutPaiement.VALIDE,
            justificatif=donnees.get("justificatif_acompte"),
        )
        db.session.add(paiement)

    historique = AnnonceHistorique(
        annonce_id=annonce.id,
        titre_annonce=annonce.titre,
        action=ActionHistorique.MODIFICATION,
        details={"type": "transaction_creee", "reference": trans.reference, "montant": float(montant_total)},
        owner_id=vendeur_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify(trans.to_dict()), 201


@bp.put("/<int:trans_id>")
def modifier_transaction(trans_id: int) -> ResponseReturnValue:
    """Met à jour une transaction immobilière."""
    trans = db.session.get(TransactionImmo, trans_id)
    if not trans:
        return jsonify({"error": "introuvable", "message": "Transaction introuvable."}), 404

    donnees = request.get_json() or {}

    if "statut" in donnees:
        trans.statut = StatutTransaction(donnees["statut"])
    if "type_transaction" in donnees:
        trans.type_transaction = TypeTransaction(donnees["type_transaction"])
    if "mode_paiement" in donnees:
        trans.mode_paiement = ModePaiement(donnees["mode_paiement"])
    if "montant_total" in donnees:
        trans.montant_total = Decimal(str(donnees["montant_total"]))
    if "acompte" in donnees:
        trans.acompte = Decimal(str(donnees["acompte"]))
    trans.reste_a_payer = trans.montant_total - (trans.acompte or Decimal(0))

    if "notaire" in donnees:
        trans.notaire = donnees["notaire"]
    if "reference_acte" in donnees:
        trans.reference_acte = donnees["reference_acte"]
    if "observations" in donnees:
        trans.observations = donnees["observations"]
    if "date_signature" in donnees and donnees["date_signature"]:
        try:
            trans.date_signature = date.fromisoformat(str(donnees["date_signature"]).split("T")[0])
        except Exception:
            pass

    db.session.commit()
    return jsonify(trans.to_dict()), 200


@bp.delete("/<int:trans_id>")
def supprimer_transaction(trans_id: int) -> ResponseReturnValue:
    """Supprime une transaction après confirmation."""
    trans = db.session.get(TransactionImmo, trans_id)
    if not trans:
        return jsonify({"error": "introuvable", "message": "Transaction introuvable."}), 404

    ref = trans.reference
    annonce_id = trans.annonce_id
    titre_annonce = trans.annonce.titre if trans.annonce else "Annonce"
    owner_id = trans.vendeur_id

    db.session.delete(trans)
    historique = AnnonceHistorique(
        annonce_id=annonce_id,
        titre_annonce=titre_annonce,
        action=ActionHistorique.SUPPRESSION,
        details={"type": "transaction_supprimee", "reference": ref},
        owner_id=owner_id,
    )
    db.session.add(historique)
    db.session.commit()

    return jsonify({"message": f"Transaction {ref} supprimée avec succès."}), 200


@bp.post("/<int:trans_id>/paiements")
def ajouter_paiement(trans_id: int) -> ResponseReturnValue:
    """Ajoute un versement/tranche à une transaction."""
    trans = db.session.get(TransactionImmo, trans_id)
    if not trans:
        return jsonify({"error": "introuvable", "message": "Transaction introuvable."}), 404

    donnees = request.get_json() or {}
    montant = Decimal(str(donnees.get("montant", 0)))
    if montant <= 0:
        return jsonify({"error": "validation", "message": "Le montant du versement doit être positif."}), 400

    nb_paiements = len(trans.paiements or [])
    ref_paiement = donnees.get("reference_paiement") or f"PAI-{trans.reference}-{nb_paiements + 1:02d}"

    paiement = Paiement(
        transaction_id=trans.id,
        montant=montant,
        mode_paiement=ModePaiement(donnees.get("mode_paiement", trans.mode_paiement)),
        reference_paiement=ref_paiement,
        statut=StatutPaiement(donnees.get("statut", "valide")),
        justificatif=donnees.get("justificatif"),
    )
    db.session.add(paiement)

    # Mettre à jour l'acompte et le reste à payer
    if paiement.statut == StatutPaiement.VALIDE:
        trans.acompte = (trans.acompte or Decimal(0)) + montant
        trans.reste_a_payer = max(Decimal(0), trans.montant_total - trans.acompte)
        if trans.reste_a_payer == Decimal(0):
            trans.statut = StatutTransaction.FINALISEE
        else:
            trans.statut = StatutTransaction.PAYEE_PARTIELLEMENT

    db.session.commit()
    return jsonify(trans.to_dict()), 201
