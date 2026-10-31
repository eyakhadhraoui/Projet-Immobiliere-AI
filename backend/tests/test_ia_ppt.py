"""Tests de l'intégration du jeu « Property Prices in Tunisia » à l'estimation du prix (IA-ANNONCE-PPT-001).

Un CSV SYNTHÉTIQUE au format du vrai fichier est construit à partir des annonces de démonstration : les tests ne
dépendent pas du vrai fichier (non versionné, licence non vérifiée).
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from app.ia import donnees_ppt, estimation_prix
from app.ia.donnees_demo import en_dict, generer_annonces
from app.schemas.ia_schema import EstimationPrixSchema

CATEGORIES = {"appartement": "Appartements", "studio": "Appartements", "residence": "Appartements",
              "maison": "Maisons et Villas", "villa": "Maisons et Villas"}
TRANSACTIONS = {"location": "À Louer", "vente": "À Vendre"}
EN_TETE = ["category", "room_count", "bathroom_count", "size", "type", "price", "city", "region", "log_price"]
# Lignes que l'import doit écarter (une par règle), ajoutées après les annonces.
LIGNES_ECARTEES = [
    ["Terrains et Fermes", -1, -1, -1, "À Vendre", 100000, "Ariana", "Raoued", 5.0],     # hors périmètre
    ["Appartements", 2, 1, -1, "À Vendre", 150000, "Ariana", "Ennasr", 5.2],              # surface inconnue
    ["Appartements", 2, -1, 80, "À Vendre", 150000, "Ariana", "Ennasr", 5.2],             # salles de bain inconnues
    ["Appartements", 2, 1, 80, "À Louer", 90, "Ariana", "Ennasr", 1.95],                  # loyer à la nuit
]
ESTIMATION = {"type_bien": "appartement", "transaction": "location", "ville": "La Marsa", "surface": 90,
              "nb_pieces": 3, "meuble": True, "caracteristiques": ["climatisation"], "nb_sdb": 2}


def ecrire_csv_ppt(chemin: Path, nombre: int = 500, graine: int = 11) -> Path:
    """CSV au format « Property Prices in Tunisia » construit à partir d'annonces de démonstration."""
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(EN_TETE)
        for numero, annonce in enumerate(generer_annonces(nombre, graine=graine)):
            region = "Autres villes" if numero % 25 == 0 else annonce.ville  # ville = gouvernorat dans ce cas
            ecrivain.writerow([CATEGORIES[annonce.type_bien], float(annonce.nb_pieces),
                               float(max(1, annonce.nb_pieces // 2)), float(annonce.surface),
                               TRANSACTIONS[annonce.transaction], float(annonce.prix), "Gouvernorat Test", region,
                               math.log10(annonce.prix)])
        ecrivain.writerows(LIGNES_ECARTEES)
    return chemin


@pytest.fixture(autouse=True)
def caches_vides():
    """Vide les caches du module entre les tests."""
    estimation_prix._cache_modeles.clear()
    estimation_prix._cache_positions.clear()
    yield
    estimation_prix._cache_modeles.clear()
    estimation_prix._cache_positions.clear()


@pytest.fixture(scope="session")
def csv_ppt(tmp_path_factory) -> Path:
    """CSV synthétique écrit une fois pour la session."""
    return ecrire_csv_ppt(tmp_path_factory.mktemp("ppt") / "Property Prices in Tunisia.csv")


@pytest.fixture(scope="session")
def modeles_ppt(tmp_path_factory, csv_ppt) -> tuple[Path, dict, dict]:
    """Modèles de démonstration (avant) puis modèles réels (après) entraînés dans le même dossier."""
    dossier = tmp_path_factory.mktemp("modeles_ppt")
    demo = [en_dict(a) for a in generer_annonces(240, graine=7)]
    estimation_prix.entrainer(demo, dossier, nb_arbres=20, nb_plis=3)
    estimation_prix._cache_modeles.clear()
    avant = estimation_prix.charger(dossier)
    annonces, rapport = donnees_ppt.lire(csv_ppt)
    meta = estimation_prix.entrainer(
        annonces, dossier, nb_arbres=20, nb_plis=3, source={**rapport, "licence": "non vérifiée"},
        ajustements=estimation_prix.ajustements_demo(demo), modeles_avant=avant)
    estimation_prix._cache_modeles.clear()
    return dossier, meta, avant


class TestImport:
    """Lecture et adaptation du CSV."""

    def test_regles_d_import(self, csv_ppt):
        annonces, rapport = donnees_ppt.lire(csv_ppt)
        assert rapport["ecartees"] == {"categorie_hors_perimetre": 1, "surface_ou_pieces_inconnues": 1,
                                       "salles_de_bain_inconnues": 1, "loyer_a_la_nuit": 1}
        assert rapport["nb_lignes"] == len(annonces) + 4
        assert {a["type_bien"] for a in annonces} == {"appartement", "maison"}
        assert all(not a["meuble"] and a["caracteristiques"] == [] for a in annonces)
        assert all(a["transaction"] != "location" or a["prix"] >= donnees_ppt.LOYER_MIN for a in annonces)
        assert len(rapport["sha256"]) == 64

    def test_ville_region_sinon_gouvernorat(self, csv_ppt):
        annonces, _ = donnees_ppt.lire(csv_ppt)
        assert annonces[0]["ville"] == "Gouvernorat Test"  # ligne 0 : région « Autres villes »
        assert annonces[1]["ville"] != "Gouvernorat Test"
        assert annonces[0]["titre"] == "PPT ligne 2"  # numéro de ligne du CSV (ligne 1 = en-tête)

    def test_fichier_absent_ou_colonne_manquante(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            donnees_ppt.lire(tmp_path / "absent.csv")
        incomplet = tmp_path / "incomplet.csv"
        incomplet.write_text("category,price\nAppartements,100\n", encoding="utf-8")
        with pytest.raises(ValueError, match="room_count"):
            donnees_ppt.lire(incomplet)


class TestAdaptation:
    """Adaptation des annonces au modèle (types, salles de bain)."""

    MODELE_REEL = {"types_equivalents": estimation_prix.TYPES_EQUIVALENTS_REELS,
                   "sdb_par_defaut": {"par_pieces": {3: 2.0}, "global": 1.0}}

    def test_types_et_salles_de_bain_imputees(self):
        villa = {**ESTIMATION, "type_bien": "villa", "nb_sdb": None}
        adaptee = estimation_prix.adapter_au_modele([villa, {**villa, "nb_pieces": 9}], self.MODELE_REEL)
        assert [a["type_bien"] for a in adaptee] == ["maison", "maison"]
        assert [a["nb_sdb"] for a in adaptee] == [2.0, 1.0]  # médiane pour 3 pièces, sinon médiane globale
        assert villa["type_bien"] == "villa" and villa["nb_sdb"] is None  # original non modifié

    def test_modele_de_demonstration_sans_salles_de_bain(self):
        adaptee = estimation_prix.adapter_au_modele([ESTIMATION], {})
        assert "nb_sdb" not in adaptee[0]
        assert "nb_sdb" not in estimation_prix.vers_tableau(adaptee)

    def test_colonne_seulement_si_toutes_renseignees(self):
        assert "nb_sdb" in estimation_prix.vers_tableau([ESTIMATION, ESTIMATION])
        assert "nb_sdb" not in estimation_prix.vers_tableau([ESTIMATION, {**ESTIMATION, "nb_sdb": None}])


class TestAjustementsDemo:
    """Effets du meublé et des équipements repris de la démonstration."""

    def test_effets_positifs_et_signe_contraire_mis_a_zero(self):
        ajustements = estimation_prix.ajustements_demo([en_dict(a) for a in generer_annonces(240, graine=7)])
        for transaction in ("location", "vente"):
            effets = ajustements[transaction]["effets"]
            assert set(effets) == set(estimation_prix.COLONNES_AJUSTABLES)
            assert all(c >= 0 for c in effets.values())
            assert all(effets[col] == 0 for col in ajustements[transaction]["mis_a_zero"])
        assert ajustements["location"]["effets"]["meuble"] > 0  # règle forte des données : meublé = plus cher

    def test_trop_peu_d_annonces(self):
        assert estimation_prix.ajustements_demo([en_dict(a) for a in generer_annonces(10)]) == {}


class TestEntrainementReel:
    """Entraînement sur les annonces réelles et comparaison avant / après."""

    def test_metadonnees_et_fiche(self, modeles_ppt):
        dossier, meta, _ = modeles_ppt
        assert meta["source"]["type"] == estimation_prix.SOURCE_REELLE
        assert meta["source"]["licence"] == "non vérifiée"
        assert "nb_sdb" in meta["variables"]
        fiche = (dossier / estimation_prix.FICHIER_FICHE).read_text(encoding="utf-8")
        assert "annonces réelles" in fiche and "Licence du jeu de données : non vérifiée" in fiche
        assert "Comparaison avant / après" in fiche and "Effets repris des données de démonstration" in fiche
        assert "données de démonstration générées par des règles" not in fiche
        assert json.loads((dossier / estimation_prix.FICHIER_METADONNEES).read_text(encoding="utf-8"))["source"]

    def test_avant_apres_sur_les_memes_annonces_de_test(self, modeles_ppt, csv_ppt):
        _, meta, avant = modeles_ppt
        utilisables, _ = estimation_prix.preparer_donnees(donnees_ppt.lire(csv_ppt)[0])
        for transaction, infos in meta["transactions"].items():
            comparaison = infos["comparaison_avant_apres"]
            assert comparaison["nb_test"] == infos["nb_test"]
            # Séparation refaite indépendamment (même appel que entrainer_transaction) : l'ancien modèle doit
            # avoir été évalué sur exactement ces annonces de test.
            sous_ensemble = [a for a in utilisables if a["transaction"] == transaction]
            _, pos_test = train_test_split(np.arange(len(sous_ensemble)), test_size=estimation_prix.PART_TEST,
                                           random_state=estimation_prix.GRAINE)
            test = [sous_ensemble[i] for i in pos_test]
            logs, _, _ = estimation_prix._predire_lot(
                avant[transaction], estimation_prix.vers_tableau(estimation_prix.adapter_au_modele(test, avant[transaction])))
            prix = np.exp(np.log([float(a["prix"]) for a in test]))  # même calcul que l'entraînement (exp(log))
            attendu = estimation_prix.mesures(prix, np.exp(logs))
            assert {k: comparaison["avant"][k] for k in attendu} == attendu
            assert comparaison["avant"]["source"] == estimation_prix.SOURCE_DEMO
            assert comparaison["apres"]["source"] == estimation_prix.SOURCE_REELLE
            assert comparaison["apres"]["mape"] == infos["scores_test"][infos["modele_retenu"]]["mape"]
            assert comparaison["baseline"] == infos["scores_test"]["baseline"]

    def test_sans_modele_avant_pas_de_comparaison(self, tmp_path, csv_ppt):
        annonces, rapport = donnees_ppt.lire(csv_ppt)
        meta = estimation_prix.entrainer(annonces, tmp_path, nb_arbres=5, nb_plis=2, source=rapport)
        assert all(i["comparaison_avant_apres"] is None for i in meta["transactions"].values())
        assert all(i["ajustements_demo"] == {"effets_pourcent": {}, "mis_a_zero": []}
                   for i in meta["transactions"].values())

    def test_demonstration_inchangee(self, tmp_path):
        meta = estimation_prix.entrainer([en_dict(a) for a in generer_annonces(180, graine=7)], tmp_path,
                                         nb_arbres=5, nb_plis=2)
        assert meta["source"]["type"] == estimation_prix.SOURCE_DEMO and "nb_sdb" not in meta["variables"]
        assert all(i["comparaison_avant_apres"] is None and i["ajustements_demo"] is None
                   for i in meta["transactions"].values())


class TestEstimationReelle:
    """Estimation avec le modèle réel."""

    def test_reponse_source_reelle(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        resultat = estimation_prix.estimer(ESTIMATION, dossier)
        assert resultat["modele"]["source"] == estimation_prix.SOURCE_REELLE
        assert "annonces réelles" in resultat["avertissement"]

    def test_confiance_au_mieux_moyenne_et_seuil_recale(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        modele = estimation_prix.charger(dossier)["location"]
        bas, haut = modele["quantiles_residus"]
        typique = math.exp(haut) - math.exp(bas)
        assert modele["seuils_largeur"]["faible"] == round(
            max(estimation_prix.LARGEUR_FAIBLE, estimation_prix.FACTEUR_LARGEUR_REELLE * typique), 3)
        resultat = estimation_prix.estimer(ESTIMATION, dossier)
        assert resultat["confiance"]["niveau"] in ("moyenne", "faible")
        assert any("Fourchette" in r for r in resultat["confiance"]["raisons"])

    def test_effet_du_meuble_repris_de_la_demo_et_signale(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        modele = estimation_prix.charger(dossier)["location"]
        meuble = estimation_prix.estimer({**ESTIMATION, "caracteristiques": []}, dossier)
        non_meuble = estimation_prix.estimer({**ESTIMATION, "caracteristiques": [], "meuble": False}, dossier)
        assert meuble["prix_estime"] > non_meuble["prix_estime"]
        effet = round((math.exp(modele["ajustements"]["meuble"]) - 1) * 100)
        attendu = {"libelle": "Meublé" + estimation_prix.MENTION_AJUSTEMENT, "effet_pourcent": effet}
        tous = estimation_prix.estimer_avec_modele({**ESTIMATION, "caracteristiques": []}, modele, {})["facteurs"]
        assert attendu in tous or abs(effet) < estimation_prix.EFFET_MIN_POURCENT

    def test_villa_estimee_comme_maison_confiance_moyenne_au_plus(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        villa = {**ESTIMATION, "type_bien": "villa", "transaction": "vente", "surface": 250, "nb_pieces": 5}
        maison = {**villa, "type_bien": "maison"}
        resultat = estimation_prix.estimer(villa, dossier)
        assert resultat["prix_estime"] == estimation_prix.estimer(maison, dossier)["prix_estime"]
        assert resultat["confiance"]["niveau"] != "élevée"
        assert any("estimé comme « Maison »" in r for r in resultat["confiance"]["raisons"])

    def test_salles_de_bain_facultatives(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        sans = estimation_prix.estimer({**ESTIMATION, "nb_sdb": None}, dossier)
        hors_plage = estimation_prix.estimer({**ESTIMATION, "nb_sdb": 15}, dossier)
        assert sans["prix_estime"] > 0
        assert hors_plage["confiance"]["niveau"] == "faible"
        assert any("15 salle(s) de bain" in r for r in hors_plage["confiance"]["raisons"])

    def test_badges_sans_salles_de_bain(self, modeles_ppt):
        dossier, _, _ = modeles_ppt
        annonce = {**ESTIMATION, "id": 1, "prix": 900, "updated_at": "x"}
        annonce.pop("nb_sdb")
        assert set(estimation_prix.positions_marche([annonce], dossier)) <= {1}

    def test_ancien_modele_de_demonstration_toujours_utilisable(self, tmp_path):
        estimation_prix.entrainer([en_dict(a) for a in generer_annonces(180, graine=7)], tmp_path,
                                  nb_arbres=5, nb_plis=2)
        resultat = estimation_prix.estimer(ESTIMATION, tmp_path)  # nb_sdb envoyé mais ignoré
        assert resultat["modele"]["source"] == estimation_prix.SOURCE_DEMO
        assert not any("salle" in f["libelle"] for f in resultat["facteurs"])


class TestSchema:
    """Champ facultatif « salles de bain » de POST /api/ia/estimation-prix."""

    def test_facultatif_et_borne(self):
        schema = EstimationPrixSchema()
        sans = {k: v for k, v in ESTIMATION.items() if k != "nb_sdb"}
        assert schema.load(sans)["nb_sdb"] is None
        assert schema.load(ESTIMATION)["nb_sdb"] == 2
        assert "nb_sdb" in schema.validate({**ESTIMATION, "nb_sdb": 21})
        assert "nb_sdb" in schema.validate({**ESTIMATION, "nb_sdb": "2"})


class TestCommande:
    """flask --app run entrainer-prix --source ppt."""

    def test_entrainement_ppt(self, app, tmp_path):
        runner = app.test_cli_runner()
        runner.invoke(args=["seed-annonces", "--nombre", "160"])
        assert runner.invoke(args=["entrainer-prix", "--arbres", "5", "--plis", "2"]).exit_code == 0  # « avant »
        chemin = ecrire_csv_ppt(tmp_path / "ppt.csv", nombre=300)
        resultat = runner.invoke(args=["entrainer-prix", "--source", "ppt", "--fichier", str(chemin),
                                       "--arbres", "5", "--plis", "2"])
        assert resultat.exit_code == 0, resultat.output
        for attendu in ("Source : Property Prices in Tunisia", "licence : non vérifiée", "écartées à l'import",
                        "Avant / après sur les mêmes", "Effets repris de la démonstration", "prix AFFICHÉS"):
            assert attendu in resultat.output
        resultat.output.encode("cp1252")  # console Windows

    def test_fichier_obligatoire_ou_introuvable(self, app, tmp_path):
        runner = app.test_cli_runner()
        assert "--fichier est obligatoire" in runner.invoke(args=["entrainer-prix", "--source", "ppt"]).output
        resultat = runner.invoke(args=["entrainer-prix", "--source", "ppt", "--fichier", str(tmp_path / "x.csv")])
        assert resultat.exit_code != 0 and "Fichier introuvable" in resultat.output


class TestVilles:
    """GET /api/ia/villes : suggestions du champ « Ville » (public)."""

    def test_liste_vide_sans_modele(self, client):
        reponse = client.get("/api/ia/villes")
        assert reponse.status_code == 200 and reponse.get_json() == {"villes": []}

    def test_villes_du_modele_triees_avec_effectifs(self, app, client, modeles_ppt):
        import shutil
        dossier, meta, _ = modeles_ppt
        shutil.copytree(dossier, app.config["MODELES_FOLDER"], dirs_exist_ok=True)
        villes = client.get("/api/ia/villes").get_json()["villes"]
        noms = [v["nom"] for v in villes]
        attendus = set(meta["transactions"]["location"]["villes"]) | set(meta["transactions"]["vente"]["villes"])
        assert set(noms) == attendus and len(noms) == len(attendus)
        assert noms == sorted(noms, key=estimation_prix.normaliser_ville)
        assert sum(v["nb_annonces"] for v in villes) == sum(
            i["nb_entrainement"] for i in meta["transactions"].values())
