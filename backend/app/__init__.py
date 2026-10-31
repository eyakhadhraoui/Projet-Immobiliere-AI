from typing import Any

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from .config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Crée et configure l'application Flask.

    Args:
        test_config: Valeurs de configuration qui remplacent celles de ``Config``
            (utilisé par les tests, ex. base SQLite en mémoire).

    Returns:
        Flask: L'application configurée.
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    migrate.init_app(app, db)
    from . import models  # noqa: F401  # enregistre les modèles pour Flask-Migrate
    CORS(app, origins=["http://localhost:5173"])

    from .commandes import (entrainer_anomalies_annonces, evaluer_anomalies_annonces,
                            entrainer_connexions, entrainer_prix, evaluer_connexions,
                            evaluer_kaggle, nettoyer_connexions, seed_annonces, seed_utilisateurs,
                            evaluer_fiabilite, installer_modele_fiabilite,
                            evaluer_test_externe, rapport_fiabilite, moderer_annonce, preparer_demo,
                            entrainer_absence_visites, entrainer_classement_annonces,
                            evaluer_classement_annonces)
    from .errors import RequeteFr, register_error_handlers
    from .routes.annonces import bp as annonces_bp
    from .routes.fiabilite import bp as fiabilite_bp
    from .routes.auth import bp as auth_bp
    from .routes.historique import bp as historique_bp
    from .routes.ia import bp as ia_bp
    from .routes.locations import bp as locations_bp
    from .routes.maintenance import bp as maintenance_bp
    from .routes.maintenance_ia import bp as maintenance_ia_bp
    from .routes.maintenance_diagnostic import bp as maintenance_diagnostic_bp
    from .routes.rag import bp as rag_bp
    from .routes.dossiers_litige import bp as dossiers_litige_bp
    from .routes.reclamations import bp as reclamations_bp
    from .routes.transactions import bp as transactions_bp
    from .routes.uploads import bp as uploads_bp
    from .routes.utilisateurs import bp as utilisateurs_bp
    from .routes.visites import bp as visites_bp

    app.json.ensure_ascii = False  # accents lisibles dans le JSON (é au lieu de \u00e9)
    app.request_class = RequeteFr
    app.register_blueprint(annonces_bp)
    app.register_blueprint(fiabilite_bp)
    app.register_blueprint(historique_bp)
    app.register_blueprint(ia_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(rag_bp)
    app.register_blueprint(dossiers_litige_bp)
    app.register_blueprint(visites_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(maintenance_ia_bp)
    app.register_blueprint(maintenance_diagnostic_bp)
    app.register_blueprint(reclamations_bp)
    app.register_blueprint(utilisateurs_bp)
    register_error_handlers(app)

    # En environnement de test, créer le schéma simplifie les tests unitaires.
    # Pour les autres environnements, le schéma doit être géré par Flask-Migrate
    # (`flask --app run db upgrade`) afin que les migrations restent la source de vérité.
    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    from .securite import init_securite

    init_securite(app)  # JWT : refuse de démarrer sans JWT_SECRET_KEY
    app.cli.add_command(seed_utilisateurs)
    app.cli.add_command(seed_annonces)
    app.cli.add_command(entrainer_prix)
    app.cli.add_command(evaluer_kaggle)
    app.cli.add_command(entrainer_connexions)
    app.cli.add_command(evaluer_connexions)
    app.cli.add_command(nettoyer_connexions)
    app.cli.add_command(entrainer_anomalies_annonces)
    app.cli.add_command(evaluer_anomalies_annonces)
    app.cli.add_command(evaluer_fiabilite)
    app.cli.add_command(evaluer_test_externe)
    app.cli.add_command(installer_modele_fiabilite)
    app.cli.add_command(rapport_fiabilite)
    app.cli.add_command(moderer_annonce)
    app.cli.add_command(preparer_demo)
    app.cli.add_command(entrainer_absence_visites)
    app.cli.add_command(entrainer_classement_annonces)
    app.cli.add_command(evaluer_classement_annonces)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
