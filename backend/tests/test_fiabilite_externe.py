"""Validation du format strict du petit jeu externe de paraphrases."""

from pathlib import Path

import pytest

from app.ia.fiabilite.externe import JeuExterneInvalide, charger_paires


def test_jeu_externe_fourni_est_equilibre_et_conserve_les_marqueurs_humains():
    fichier = Path(__file__).resolve().parents[2] / "docs" / "test-externe-paraphrases.txt"
    paires = charger_paires(fichier)
    assert len(paires) == 20
    assert sum(paire["doublon"] for paire in paires) == 10
    assert sum(paire["humain"] for paire in paires) == 0


def test_jeu_externe_refuse_un_nombre_de_paires_invalide(tmp_path):
    fichier = tmp_path / "jeu.txt"
    fichier.write_text("DOUBLON\nA: texte alpha\nB: texte beta\n", encoding="utf-8")
    with pytest.raises(JeuExterneInvalide, match="Il faut 20 paires"):
        charger_paires(fichier)
