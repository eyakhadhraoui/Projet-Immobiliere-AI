"""Tests de la commande « flask seed-utilisateurs »."""

from __future__ import annotations

from sqlalchemy import select

from app import db
from app.commandes import EMAIL_DEMO
from app.models import Utilisateur
from tests.outils import mot_de_passe_aleatoire

MOT_DE_PASSE_DEMO = mot_de_passe_aleatoire()  # généré à chaque exécution, jamais écrit dans le code
SAISIE = f"{MOT_DE_PASSE_DEMO}\n{MOT_DE_PASSE_DEMO}\n"  # saisie puis confirmation


def comptes(app) -> list[Utilisateur]:
    """Tous les comptes de la base de test."""
    with app.app_context():
        return db.session.scalars(select(Utilisateur)).all()


def test_cree_un_proprietaire_avec_le_mot_de_passe_saisi(app):
    # Act : le mot de passe est saisi deux fois (confirmation)
    resultat = app.test_cli_runner().invoke(args=["seed-utilisateurs"], input=SAISIE)
    # Assert
    assert resultat.exit_code == 0, resultat.output
    assert f"Propriétaire de démonstration créé : {EMAIL_DEMO}" in resultat.output
    assert MOT_DE_PASSE_DEMO not in resultat.output  # saisie masquée
    (compte,) = comptes(app)
    assert compte.role.value == "proprietaire"
    assert compte.verifier_mot_de_passe(MOT_DE_PASSE_DEMO)


def test_mot_de_passe_faible_refuse(app):
    # Act : « faible » est un exemple refusé par la politique (8 caractères, lettres et chiffres)
    resultat = app.test_cli_runner().invoke(args=["seed-utilisateurs"], input="faible\nfaible\n")
    # Assert
    assert resultat.exit_code == 1
    assert "Mot de passe refusé" in resultat.output
    assert comptes(app) == []


def test_ne_recree_pas_un_compte_existant(app):
    # Arrange
    runner = app.test_cli_runner()
    runner.invoke(args=["seed-utilisateurs", "--email", "Demo@Example.com"], input=SAISIE)
    # Act
    resultat = runner.invoke(args=["seed-utilisateurs", "--email", "demo@example.com"])
    # Assert
    assert resultat.exit_code == 0
    assert "Un compte existe déjà avec l'email demo@example.com" in resultat.output
    assert len(comptes(app)) == 1
