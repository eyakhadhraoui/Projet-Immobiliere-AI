"""Statistiques et agrégats pour le tableau de bord de l'espace propriétaire."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app import db
from app.models import (
    Annonce,
    DemandeMaintenance,
    LocationImmo,
    Loyer,
    PrioriteMaintenance,
    Reclamation,
    StatutAnnonce,
    StatutLocation,
    StatutMaintenance,
    StatutLoyer,
    StatutReclamation,
    StatutTransaction,
    StatutVisite,
    Transaction,
    TransactionImmo,
    TypeBien,
    Visite,
)
from app.services.historique_service import dernieres_actions
from app.services.planification_absence import donnees_carte_chaleur

NB_DERNIERES_ACTIONS = 5


def _compter_par(colonne: Any, valeurs: type[StatutAnnonce] | type[TypeBien], owner_id: int) -> dict[str, int]:
    """Compte les annonces par valeur d'une colonne Enum (0 pour les valeurs absentes)."""
    comptes = {valeur.value: 0 for valeur in valeurs}
    requete = select(colonne, func.count()).where(Annonce.owner_id == owner_id).group_by(colonne)
    for valeur, nombre in db.session.execute(requete):
        comptes[valeur.value] = nombre
    return comptes


def calculer_statistiques(owner_id: int) -> dict[str, Any]:
    """Calcule les statistiques globales du propriétaire pour le tableau de bord."""
    prix_moyen: dict[str, float | None] = {transaction.value: None for transaction in Transaction}
    requete_prix = (
        select(Annonce.transaction, func.avg(Annonce.prix))
        .where(Annonce.owner_id == owner_id)
        .group_by(Annonce.transaction)
    )
    for transaction, moyenne in db.session.execute(requete_prix):
        prix_moyen[transaction.value] = round(float(moyenne), 2)

    total_annonces = db.session.scalar(select(func.count()).select_from(Annonce).where(Annonce.owner_id == owner_id)) or 0

    # Visites en attente
    visites_en_attente = db.session.scalar(
        select(func.count()).select_from(Visite).where(
            Visite.proprietaire_id == owner_id,
            Visite.statut == StatutVisite.EN_ATTENTE,
        )
    ) or 0

    # Loyers en retard
    loyers_en_retard = db.session.scalar(
        select(func.count()).select_from(Loyer).join(LocationImmo).where(
            LocationImmo.proprietaire_id == owner_id,
            Loyer.statut == StatutLoyer.EN_RETARD,
        )
    ) or 0

    # Transactions en cours
    transactions_en_cours = db.session.scalar(
        select(func.count()).select_from(TransactionImmo).where(
            TransactionImmo.vendeur_id == owner_id,
            TransactionImmo.statut.in_([
                StatutTransaction.EN_COURS,
                StatutTransaction.EN_NEGOCIATION,
                StatutTransaction.RESERVEE,
                StatutTransaction.PAYEE_PARTIELLEMENT,
            ]),
        )
    ) or 0

    # Réclamations ouvertes
    reclamations_ouvertes = db.session.scalar(
        select(func.count()).select_from(Reclamation).where(
            Reclamation.statut.in_([
                StatutReclamation.NOUVELLE,
                StatutReclamation.EN_COURS,
                StatutReclamation.EN_ATTENTE_INFO,
            ]),
        )
    ) or 0

    statuts_maintenance_ouverts = [
        StatutMaintenance.SIGNALEE,
        StatutMaintenance.ACCEPTEE,
        StatutMaintenance.ASSIGNEE,
        StatutMaintenance.PLANIFIEE,
    ]
    maintenances_ouvertes = db.session.scalar(
        select(func.count()).select_from(DemandeMaintenance).where(
            DemandeMaintenance.proprietaire_id == owner_id,
            DemandeMaintenance.statut.in_(statuts_maintenance_ouverts),
        )
    ) or 0
    maintenances_urgentes = db.session.scalar(
        select(func.count()).select_from(DemandeMaintenance).where(
            DemandeMaintenance.proprietaire_id == owner_id,
            DemandeMaintenance.statut.in_(statuts_maintenance_ouverts),
            DemandeMaintenance.priorite == PrioriteMaintenance.URGENTE,
        )
    ) or 0

    # Prochaines visites
    prochaines_visites_db = db.session.scalars(
        select(Visite)
        .where(Visite.proprietaire_id == owner_id)
        .order_by(Visite.date_visite.asc(), Visite.heure_debut.asc())
        .limit(5)
    ).all()
    prochaines_visites = [v.to_dict() for v in prochaines_visites_db]

    # Loyers à encaisser
    loyers_db = db.session.scalars(
        select(Loyer)
        .join(LocationImmo)
        .where(LocationImmo.proprietaire_id == owner_id)
        .order_by(Loyer.date_echeance.asc())
        .limit(5)
    ).all()
    loyers_a_encaisser = []
    for l in loyers_db:
        d = l.to_dict()
        d["titre_bien"] = l.location.annonce.titre if l.location and l.location.annonce else "Bien"
        loyers_a_encaisser.append(d)

    return {
        "total": total_annonces,
        "par_statut": _compter_par(Annonce.statut, StatutAnnonce, owner_id),
        "par_type": _compter_par(Annonce.type_bien, TypeBien, owner_id),
        "prix_moyen": prix_moyen,
        "visites_en_attente": visites_en_attente,
        "loyers_en_retard": loyers_en_retard,
        "transactions_en_cours": transactions_en_cours,
        "reclamations_ouvertes": reclamations_ouvertes,
        "maintenances_ouvertes": maintenances_ouvertes,
        "maintenances_urgentes": maintenances_urgentes,
        "taux_absence_jour_heure": donnees_carte_chaleur(owner_id),
        "messages_non_lus": 5,
        "prochaines_visites": prochaines_visites,
        "loyers_a_encaisser": loyers_a_encaisser,
        "dernieres_actions": dernieres_actions(owner_id, NB_DERNIERES_ACTIONS),
    }
