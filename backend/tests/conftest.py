"""Fixtures pytest : application de test sur une base SQLite en mémoire."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app, db
from tests.outils import MOT_DE_PASSE, ClientNavigateur


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Flask]:
    """Application de test : base SQLite en mémoire et dossier d'uploads temporaire, neufs pour chaque test.

    Args:
        tmp_path: Dossier temporaire fourni par pytest (jamais ``backend/uploads``).

    Yields:
        Flask: Application configurée pour les tests.
    """
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "MODELES_FOLDER": str(tmp_path / "modeles"),  # jamais backend/modeles pendant les tests
        "DOSSIERS_LITIGE_FOLDER": str(tmp_path / "dossiers_litige"),
        "JWT_SECRET_KEY": "cle-de-test-uniquement-pour-pytest-0123456789",  # pas un secret : base jetable
        "JWT_COOKIE_SECURE": False,
    })
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()  # ferme la connexion SQLite en mémoire (évite les ResourceWarning)


@pytest.fixture
def dossier_uploads(app: Flask) -> Path:
    """Dossier d'uploads temporaire de l'application de test.

    Args:
        app: Application de test.

    Returns:
        Path: Valeur de ``UPLOAD_FOLDER``.
    """
    return Path(app.config["UPLOAD_FOLDER"])


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Client de test Flask.

    Args:
        app: Application de test.

    Returns:
        FlaskClient: Client HTTP de test.
    """
    return app.test_client()


@pytest.fixture
def annonce_valide() -> dict[str, Any]:
    """Données d'une annonce valide pour ``POST /api/annonces``.

    Returns:
        dict[str, Any]: Corps JSON valide.
    """
    return {
        "titre": "S+2 meublé à La Marsa",
        "description": "Bel appartement proche de la plage",
        "type_bien": "appartement",
        "transaction": "location",
        "prix": 1200,
        "surface": 85,
        "nb_pieces": 3,
        "meuble": True,
        "adresse": "12 rue de la Plage",
        "ville": "La Marsa",
        "caracteristiques": ["parking", "climatisation"],
    }


@pytest.fixture
def villa_valide() -> dict[str, Any]:
    """Données d'une seconde annonce valide, différente sur tous les critères filtrables.

    Returns:
        dict[str, Any]: Corps JSON valide.
    """
    return {
        "titre": "Villa avec piscine à Sousse",
        "description": "Grande villa",
        "type_bien": "villa",
        "transaction": "vente",
        "prix": 450000,
        "surface": 320,
        "nb_pieces": 6,
        "adresse": "Route de la corniche",
        "ville": "Sousse",
        "latitude": 35.83,
        "longitude": 10.63,
    }


@pytest.fixture
def creer_annonce(client: FlaskClient) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Fabrique qui crée une annonce via l'API et renvoie son JSON.

    Args:
        client: Client de test.

    Returns:
        Callable[[dict[str, Any]], dict[str, Any]]: Fonction ``creer(donnees) -> annonce``.
    """

    def creer(donnees: dict[str, Any]) -> dict[str, Any]:
        reponse = client.post("/api/annonces", json=donnees)
        assert reponse.status_code == 201, reponse.get_json()
        return reponse.get_json()

    return creer


# --- Module utilisateurs (USER-001) ---------------------------------------------------------------

@pytest.fixture
def donnees_inscription() -> dict[str, Any]:
    """Corps valide de ``POST /api/auth/inscription`` (propriétaire).

    Returns:
        dict[str, Any]: Données d'inscription.
    """
    return {
        "nom": "Rouached",
        "prenom": "Loujain",
        "email": "loujain@example.com",
        "mot_de_passe": MOT_DE_PASSE,
        "role": "proprietaire",
        "telephone": "+216 20 123 456",
        "ville": "Tunis",
        "cin_numero": "12345678",
    }


@pytest.fixture
def compte(client: FlaskClient, donnees_inscription: dict[str, Any]) -> dict[str, Any]:
    """Compte inscrit ; le client de test est connecté (cookies de session posés).

    Args:
        client: Client de test.
        donnees_inscription: Données d'inscription.

    Returns:
        dict[str, Any]: Compte renvoyé par l'API.
    """
    reponse = client.post("/api/auth/inscription", json=donnees_inscription)
    assert reponse.status_code == 201, reponse.get_json()
    return reponse.get_json()


def _client_inscrit(app: Flask, donnees: dict[str, Any]) -> ClientNavigateur:
    """Inscrit un compte et renvoie un client connecté avec ce compte.

    Args:
        app: Application de test.
        donnees: Corps de ``POST /api/auth/inscription``.

    Returns:
        ClientNavigateur: Client connecté (cookies de session + en-tête CSRF automatique).
    """
    client_connecte = ClientNavigateur(app, app.response_class, use_cookies=True)
    reponse = client_connecte.post("/api/auth/inscription", json=donnees)
    assert reponse.status_code == 201, reponse.get_json()
    return client_connecte


@pytest.fixture
def client_proprietaire(app: Flask, donnees_inscription: dict[str, Any]) -> ClientNavigateur:
    """Client connecté en tant que propriétaire (premier compte : id 1 dans une base neuve).

    Args:
        app: Application de test.
        donnees_inscription: Données d'inscription (propriétaire).

    Returns:
        ClientNavigateur: Client connecté.
    """
    return _client_inscrit(app, donnees_inscription)


@pytest.fixture
def client_autre_proprietaire(app: Flask, donnees_inscription: dict[str, Any]) -> ClientNavigateur:
    """Client connecté avec un second propriétaire.

    Args:
        app: Application de test.
        donnees_inscription: Données d'inscription de base.

    Returns:
        ClientNavigateur: Client connecté.
    """
    return _client_inscrit(app, {**donnees_inscription, "prenom": "Sami", "email": "sami@example.com", "cin_numero": None})


@pytest.fixture
def client_client(app: Flask, donnees_inscription: dict[str, Any]) -> ClientNavigateur:
    """Client connecté avec un compte au rôle « client » (pas propriétaire).

    Args:
        app: Application de test.
        donnees_inscription: Données d'inscription de base.

    Returns:
        ClientNavigateur: Client connecté.
    """
    return _client_inscrit(app, {
        **donnees_inscription, "prenom": "Ines", "email": "ines@example.com", "role": "client", "cin_numero": None,
    })
