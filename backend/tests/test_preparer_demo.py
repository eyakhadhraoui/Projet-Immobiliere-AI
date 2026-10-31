"""Tests de la commande preparer-demo (Prompt 12 de fiabilité)."""

from pathlib import Path

from click.testing import CliRunner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import db
from app.commandes import preparer_demo
from app.models import (Annonce, AnnoncePhoto, RoleUtilisateur, StatutAnnonce,
                        Transaction, TypeBien, Utilisateur)


def _creer_base_sqlite_vierge(chemin: Path) -> None:
    """Initialise le schéma de base de données complet dans un fichier SQLite."""
    engine = create_engine(f"sqlite:///{chemin.resolve()}")
    db.metadata.create_all(engine)
    engine.dispose()


def test_base_inexistante_refusee(app):
    runner = CliRunner()
    result = runner.invoke(preparer_demo, ["--base", "chemin/inconnu/base.db"], obj={})
    assert result.exit_code != 0
    assert "Base SQLite introuvable" in result.output


def test_base_principale_refusee_sans_confirmer(app, tmp_path, monkeypatch):
    base_principale = Path(app.instance_path) / "immobilier.db"
    base_principale.parent.mkdir(parents=True, exist_ok=True)
    base_principale.touch()

    runner = CliRunner()
    result = runner.invoke(preparer_demo, ["--base", str(base_principale)], obj={})
    assert result.exit_code != 0
    assert "Refus de modifier la base principale sans --confirmer" in result.output


def test_mot_de_passe_non_conforme_refuse(app, tmp_path, monkeypatch):
    base_test = tmp_path / "test_demo.db"
    _creer_base_sqlite_vierge(base_test)

    monkeypatch.setenv("DEMO_MOT_DE_PASSE", "court")
    runner = CliRunner()
    result = runner.invoke(preparer_demo, ["--base", str(base_test)], obj={})
    assert result.exit_code != 0
    assert "Mot de passe refusé" in result.output


def test_preparation_nominale_et_donnees_identiques_e2e(app, tmp_path, monkeypatch):
    base_test = tmp_path / "demo_e2e.db"
    _creer_base_sqlite_vierge(base_test)
    uploads_dir = tmp_path / "uploads"
    photos_dir = tmp_path / "photos"

    mot_de_passe = "P@ssw0rd2026!Securise"
    monkeypatch.setenv("DEMO_MOT_DE_PASSE", mot_de_passe)

    runner = CliRunner()
    result = runner.invoke(preparer_demo, [
        "--base", str(base_test),
        "--uploads", str(uploads_dir),
        "--photos-demo", str(photos_dir),
    ], obj={})

    assert result.exit_code == 0
    # Mot de passe jamais affiché dans les logs
    assert mot_de_passe not in result.output
    assert "Base de démonstration prête" in result.output

    # Vérification des photos de démonstration générées
    for nom in ("photo1.jpg", "photo2.jpg", "photo3.jpg", "photo4.jpg", "photo1_miroir.jpg"):
        assert (photos_dir / nom).is_file()

    # Vérification dans la base SQLite cible
    engine = create_engine(f"sqlite:///{base_test.resolve()}")
    with Session(engine) as session:
        comptes = session.scalars(select(Utilisateur)).all()
        emails = {u.email for u in comptes}
        assert emails == {"amira@test.tn", "sami@test.tn", "karim@test.tn"}
        for u in comptes:
            assert u.role == RoleUtilisateur.PROPRIETAIRE
            assert u.verifier_mot_de_passe(mot_de_passe)

        amira = session.scalar(select(Utilisateur).where(Utilisateur.email == "amira@test.tn"))
        annonces = session.scalars(select(Annonce).where(Annonce.owner_id == amira.id)).all()
        assert len(annonces) == 2

        a1 = next(a for a in annonces if "Studio" in a.titre)
        assert a1.titre == "Studio meublé pour étudiant près de la faculté"
        assert a1.type_bien == TypeBien.STUDIO
        assert a1.transaction == Transaction.LOCATION
        assert a1.prix == 450
        assert a1.surface == 30
        assert a1.nb_pieces == 1
        assert a1.meuble is True
        assert a1.ville == "Sousse"
        assert a1.statut == StatutAnnonce.PUBLIEE
        assert len(a1.photos) == 0

        a2 = next(a for a in annonces if "Maison" in a.titre)
        assert a2.titre == "Maison avec jardin et puits à Mahdia"
        assert a2.type_bien == TypeBien.MAISON
        assert a2.transaction == Transaction.LOCATION
        assert a2.prix == 1400
        assert a2.surface == 160
        assert a2.nb_pieces == 5
        assert a2.meuble is False
        assert a2.ville == "Mahdia"
        assert a2.statut == StatutAnnonce.PUBLIEE
        assert len(a2.photos) == 2

        for photo in a2.photos:
            assert photo.sha256 and len(photo.sha256) == 64
            assert photo.phash and len(photo.phash) == 16
            assert photo.url.startswith("/uploads/")

    engine.dispose()


def test_relance_sans_doublon(app, tmp_path, monkeypatch):
    base_test = tmp_path / "demo_idempotent.db"
    _creer_base_sqlite_vierge(base_test)
    uploads_dir = tmp_path / "uploads"
    photos_dir = tmp_path / "photos"

    monkeypatch.setenv("DEMO_MOT_DE_PASSE", "P@ssw0rd2026!Securise")
    runner = CliRunner()

    # Première exécution
    res1 = runner.invoke(preparer_demo, [
        "--base", str(base_test),
        "--uploads", str(uploads_dir),
        "--photos-demo", str(photos_dir),
    ], obj={})
    assert res1.exit_code == 0

    # Deuxième exécution
    res2 = runner.invoke(preparer_demo, [
        "--base", str(base_test),
        "--uploads", str(uploads_dir),
        "--photos-demo", str(photos_dir),
    ], obj={})
    assert res2.exit_code == 0

    engine = create_engine(f"sqlite:///{base_test.resolve()}")
    with Session(engine) as session:
        comptes = session.scalars(select(Utilisateur)).all()
        assert len(comptes) == 3
        annonces = session.scalars(select(Annonce)).all()
        assert len(annonces) == 2
        photos = session.scalars(select(AnnoncePhoto)).all()
        assert len(photos) == 2
    engine.dispose()
