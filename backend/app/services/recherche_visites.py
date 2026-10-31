"""Recherche de biens avec filtres stricts et créneaux visiteur compatibles."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app import db
from app.ia.classement_annonces import classer as classer_annonces
from app.models import Annonce, DisponibiliteVisite, StatutAnnonce, Visite
from app.services.planification_visites import proposer_creneaux, statuts_bloquants


def rechercher(criteres: dict[str, Any], dossier_modeles: Path) -> tuple[list[dict[str, Any]], bool]:
    """Filtre d'abord les annonces et ne classe que celles ayant un créneau demandé libre.

    Args:
        criteres: Critères validés par ``RechercheVisiteSchema``.
        dossier_modeles: Dossier local des modèles du projet.

    Returns:
        tuple: Annonces admissibles avec créneaux compatibles, et indicateur de classement ML.
    """
    requete = select(Annonce).where(Annonce.statut == StatutAnnonce.PUBLIEE)
    villes = criteres.get("villes", [])
    if villes:
        requete = requete.where(func.lower(Annonce.ville).in_([ville.casefold() for ville in villes]))
    if criteres.get("transaction"):
        requete = requete.where(Annonce.transaction == criteres["transaction"])
    if criteres.get("type_bien"):
        requete = requete.where(Annonce.type_bien == criteres["type_bien"])
    if criteres.get("budget_max") is not None:
        requete = requete.where(Annonce.prix <= criteres["budget_max"])
    if criteres.get("pieces_min") is not None:
        requete = requete.where(Annonce.nb_pieces >= criteres["pieces_min"])

    annonces = db.session.scalars(requete.order_by(Annonce.created_at.desc(), Annonce.id.desc())).all()
    if not annonces:
        return [], False

    annonce_ids = [annonce.id for annonce in annonces]
    disponibilites = db.session.scalars(select(DisponibiliteVisite).where(
        DisponibiliteVisite.annonce_id.in_(annonce_ids), DisponibiliteVisite.actif.is_(True)
    )).all()
    par_annonce: dict[int, list[DisponibiliteVisite]] = {}
    for disponibilite in disponibilites:
        par_annonce.setdefault(disponibilite.annonce_id, []).append(disponibilite)

    dates = [plage["debut"].date() for plage in criteres["disponibilites"]]
    dates.extend(plage["fin"].date() for plage in criteres["disponibilites"])
    maintenant = datetime.now().astimezone().replace(tzinfo=None)
    aujourd_hui = maintenant.date()
    visites = db.session.scalars(select(Visite).where(
        Visite.statut.in_(statuts_bloquants()),
        Visite.date_visite >= aujourd_hui,
        Visite.date_visite <= aujourd_hui + timedelta(days=14),
    )).all()
    visites_par_proprietaire: dict[int, list[Visite]] = {}
    for visite in visites:
        visites_par_proprietaire.setdefault(visite.proprietaire_id, []).append(visite)

    admissibles: list[dict[str, Any]] = []
    for annonce in annonces:
        plages_annonce = par_annonce.get(annonce.id, [])
        if not plages_annonce:
            continue
        propositions = proposer_creneaux(
            annonce, plages_annonce, visites_par_proprietaire.get(annonce.owner_id, []),
            maintenant=maintenant, nb=10000,
        )
        compatibles = [
            proposition.to_dict()
            for proposition in propositions
            if any(plage["debut"] <= proposition.debut and proposition.fin <= plage["fin"]
                   for plage in criteres["disponibilites"])
        ]
        if compatibles:
            donnees = annonce.to_dict()
            donnees["creneaux_compatibles"] = compatibles
            admissibles.append(donnees)

    if criteres.get("tri") == "chronologique":
        return admissibles, False
    filtres_modele = {
        "ville": villes[0] if len(villes) == 1 else "",
        "type_bien": criteres.get("type_bien").value if criteres.get("type_bien") else None,
        "transaction": criteres.get("transaction").value if criteres.get("transaction") else None,
        "prix_max": criteres.get("budget_max"),
        "pieces_min": criteres.get("pieces_min"),
    }
    annonces_classees, modele_disponible = classer_annonces(admissibles, filtres_modele, dossier_modeles)
    return annonces_classees, modele_disponible
