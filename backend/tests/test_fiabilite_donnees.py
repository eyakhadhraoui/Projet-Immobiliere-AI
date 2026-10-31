"""Vérifie les empreintes privées et la séparation du jeu fictif."""

from pathlib import Path

from PIL import Image

from app.ia.fiabilite.empreintes import distance_hamming, empreintes_image
from app.ia.fiabilite.jeu import charger_jeu


RACINE = Path(__file__).parent
JEU = RACINE / "donnees_fiabilite" / "jeu_annote.json"


def test_empreintes_stables_et_copie_exacte():
    contenu = (RACINE / "donnees_fiabilite" / "photos" / "S01-original.jpg").read_bytes()
    assert empreintes_image(contenu) == empreintes_image(bytes(contenu))
    sha, phash = empreintes_image(contenu)
    assert len(sha) == 64
    assert len(phash) == 16
    assert distance_hamming(phash, phash) == 0


def test_photo_reenregistree_garde_un_phash_proche():
    original = RACINE / "donnees_fiabilite" / "photos" / "S02-original.jpg"
    republiee = RACINE / "donnees_fiabilite" / "photos" / "S02-republication.jpg"
    original_sha, original_hash = empreintes_image(original.read_bytes())
    copie_sha, copie_hash = empreintes_image(republiee.read_bytes())
    assert original_sha != copie_sha
    assert distance_hamming(original_hash, copie_hash) <= 6


def test_jeu_fictif_est_separe_par_groupe():
    jeu = charger_jeu(JEU)
    assert len(jeu["annonces"]) == 234
    assert {a["ensemble"] for a in jeu["annonces"]} == {"entrainement", "validation", "test"}


def test_octets_illisibles_gardent_sha_sans_phash():
    sha, phash = empreintes_image(b"pas une image")
    assert len(sha) == 64
    assert phash is None
