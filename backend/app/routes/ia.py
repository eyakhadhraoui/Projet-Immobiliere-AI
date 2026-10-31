"""Routes de l'intelligence artificielle du module annonces (préfixe ``/api/ia``)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user
from sqlalchemy import select

from app import db
from app.errors import ModeleNonEntraine
from app.ia import anomalies_annonces, estimation_prix
from app.ia.rag.llm_client import generer_avec_gemini
from app.schemas.ia_schema import EstimationPrixSchema
from app.securite import proprietaire_requis
from app.models import Annonce

bp = Blueprint("ia", __name__, url_prefix="/api/ia")

_estimation_schema = EstimationPrixSchema()


@bp.post("/annonces/<int:annonce_id>/analyser-anomalie")
@proprietaire_requis
def anomalie_annonce_route(annonce_id: int) -> ResponseReturnValue:
    """Analyse uniquement une annonce appartenant au propriétaire connecté."""
    annonce = db.session.scalar(select(Annonce).where(Annonce.id == annonce_id))
    if annonce is None:
        return jsonify(message="Annonce introuvable."), 404
    if annonce.owner_id != current_user.id:
        return jsonify(message="Vous ne pouvez analyser que vos propres annonces."), 403
    donnees = {"prix": annonce.prix, "surface": annonce.surface, "nb_pieces": annonce.nb_pieces,
               "transaction": annonce.transaction.value, "type_bien": annonce.type_bien.value,
               "ville": annonce.ville}
    try:
        resultat = anomalies_annonces.analyser(donnees, Path(current_app.config["MODELES_FOLDER"]))
    except FileNotFoundError:
        resultat = {"disponible": False, "niveau": "indetermine", "score_anomalie": None, "facteurs": [],
                    "repli": "Le modèle n'est pas entraîné. Lancez flask --app run entrainer-anomalies-annonces."}
    except anomalies_annonces.DonneesAnnoncesInvalides as erreur:
        resultat = {"disponible": False, "niveau": "indetermine", "score_anomalie": None, "facteurs": [],
                    "repli": str(erreur)}
    return jsonify(resultat), 200

MESSAGE_MODELE_ABSENT = (
    "L'estimation du prix n'est pas encore disponible : le modèle n'a pas été entraîné "
    "(commande « flask --app run entrainer-prix »)."
)


@bp.post("/estimation-prix")
@proprietaire_requis
def estimation_prix_route() -> ResponseReturnValue:
    """Estime le prix d'un bien (propriétaire connecté) : prix, fourchette, facteurs, avertissement.

    L'IA propose, le propriétaire décide : le prix n'est jamais modifié automatiquement.

    Returns:
        ResponseReturnValue: 200 avec l'estimation ; 400, 401, 403 ; 503 si le modèle n'est pas entraîné.
    """
    donnees = _estimation_schema.load(request.get_json())
    donnees["type_bien"] = donnees["type_bien"].value
    donnees["transaction"] = donnees["transaction"].value
    try:
        resultat = estimation_prix.estimer(donnees, Path(current_app.config["MODELES_FOLDER"]))
    except estimation_prix.ModeleIndisponible as erreur:
        raise ModeleNonEntraine(MESSAGE_MODELE_ABSENT) from erreur
    return jsonify(resultat), 200


@bp.post("/description-annonce")
@proprietaire_requis
def description_annonce_route() -> ResponseReturnValue:
    """Rédige ou améliore une description à partir des seules données fournies."""
    donnees = request.get_json(silent=True) or {}
    action = donnees.get("action", "generer")
    if action not in {"generer", "ameliorer"}:
        return jsonify(message="Action invalide."), 400
    description = str(donnees.get("description", "")).strip()[:4000]
    if action == "ameliorer" and not description:
        return jsonify(message="Saisissez une description à améliorer."), 400
    champs = {
        cle: str(donnees.get(cle, "")).strip()[:300]
        for cle in ("titre", "type_bien", "transaction", "prix", "surface", "nb_pieces", "ville", "adresse")
        if donnees.get(cle) not in (None, "")
    }
    caracteristiques = donnees.get("caracteristiques", [])
    if isinstance(caracteristiques, list):
        champs["caracteristiques"] = ", ".join(str(x)[:80] for x in caracteristiques[:30])
    champs["meuble"] = "oui" if donnees.get("meuble") else "non"
    consigne = (
        "Tu es rédacteur d'annonces immobilières en Tunisie. Réponds uniquement par une description "
        "claire et professionnelle en français, en 2 à 4 phrases. Utilise uniquement les faits fournis. "
        "N'invente aucun équipement, état, avantage, vue, distance ou service. N'ajoute pas de titre, "
        "de prix ni de commentaire.\n"
        f"Action: {action}\nDonnées vérifiées: {champs}\nTexte existant: {description or '(aucun)'}"
    )
    resultat = generer_avec_gemini(consigne)
    if not resultat:
        return jsonify(message="Gemini est indisponible. Vérifiez GEMINI_API_KEY et réessayez."), 503
    return jsonify(description=resultat[:4000]), 200


@bp.get("/villes")
def villes_route() -> ResponseReturnValue:
    """Villes connues du modèle d'estimation (public) : suggestions du champ « Ville ».

    Returns:
        ResponseReturnValue: 200 avec ``{"villes": [{"nom", "nb_annonces"}]}`` (liste vide sans modèle).
    """
    return jsonify({"villes": estimation_prix.villes_connues(Path(current_app.config["MODELES_FOLDER"]))}), 200
