"""État public et minimum du moteur de fiabilité des annonces."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

from app.ia.fiabilite.texte import NOM_BASE
from app.securite import proprietaire_requis

bp = Blueprint("fiabilite", __name__, url_prefix="/api/ia/fiabilite")


@bp.get("/etat")
@proprietaire_requis
def etat_moteur() -> ResponseReturnValue:
    """Indique si l'encodeur LoRA est localement prêt ou si TF-IDF sera utilisé."""
    dossier = Path(current_app.config["MODELES_FOLDER"])
    base = dossier / "texte" / NOM_BASE
    adaptateur = dossier / "fiabilite" / "lora"
    manifest = base / "fiabilite_manifest.json"
    poids = any((base / nom).is_file() for nom in ("model.safetensors", "pytorch_model.bin"))
    pret = bool(base.is_dir() and adaptateur.is_dir() and manifest.is_file() and poids)
    if pret:
        return jsonify({"etat": "pret", "libelle": "Vérification automatique : prête",
                        "modele_texte": "minilm_lora"}), 200
    return jsonify({"etat": "indisponible", "libelle": "Méthode simplifiée (modèle local indisponible)",
                    "modele_texte": "tfidf"}), 200
