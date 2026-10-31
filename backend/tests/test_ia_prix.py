"""Tests de l'estimation du prix (IA-ANNONCE-001) : données de démonstration, entraînement, prédiction, route,
badge « bonne affaire » et commandes."""

from __future__ import annotations

import shutil
import statistics
from pathlib import Path

import pytest

from app import db
from app.ia import donnees_demo, estimation_prix
from app.ia.donnees_demo import en_dict, generer_annonces
from app.models import Annonce, Utilisateur

ESTIMATION_VALIDE = {
    "type_bien": "appartement", "transaction": "location", "ville": "La Marsa", "surface": 90,
    "nb_pieces": 3, "meuble": True, "caracteristiques": ["climatisation", "balcon"],
}


@pytest.fixture(autouse=True)
def caches_vides():
    """Vide les caches du module entre les tests (modèles et positions de marché)."""
    estimation_prix._cache_modeles.clear()
    estimation_prix._cache_positions.clear()
    yield
    estimation_prix._cache_modeles.clear()
    estimation_prix._cache_positions.clear()


@pytest.fixture(scope="session")
def modeles_entraines(tmp_path_factory) -> Path:
    """Modèles entraînés une seule fois pour toute la session (petit jeu, petite forêt : rapide)."""
    dossier = tmp_path_factory.mktemp("modeles_session")
    annonces = [en_dict(a) for a in generer_annonces(180, graine=7)]
    estimation_prix.entrainer(annonces, dossier, nb_arbres=20, nb_plis=3)
    return dossier


@pytest.fixture
def modele_dans_app(app, modeles_entraines) -> Path:
    """Copie les modèles entraînés dans le dossier MODELES_FOLDER de l'application de test."""
    dossier = Path(app.config["MODELES_FOLDER"])
    shutil.copytree(modeles_entraines, dossier, dirs_exist_ok=True)
    return dossier


class TestDonneesDemo:
    """Génération des annonces de démonstration."""

    def test_meme_graine_memes_annonces(self):
        assert generer_annonces(20, graine=1) == generer_annonces(20, graine=1)
        assert generer_annonces(20, graine=1) != generer_annonces(20, graine=2)

    def test_annonces_realistes_et_marquees(self):
        annonces = generer_annonces(300)
        assert all(a.titre.startswith("[DÉMO]") for a in annonces)
        assert {a.ville for a in annonces} <= set(donnees_demo.VILLES)
        assert sum(a.statut == "publiee" for a in annonces) / len(annonces) > 0.75
        for a in annonces:
            lat, lon, _pv, _pl = donnees_demo.VILLES[a.ville]
            assert abs(a.latitude - lat) <= 0.02 and abs(a.longitude - lon) <= 0.02
            assert 5 <= len(a.titre) <= 150 and a.surface > 0 and a.prix > 0
        assert len({a.description for a in annonces}) > 250  # descriptions variées

    def test_prix_coherents_avec_les_regles(self):
        annonces = [a for a in generer_annonces(300) if a.transaction == "vente"]
        prix_m2 = {v: statistics.median(a.prix / a.surface for a in annonces if a.ville == v)
                   for v in ("La Marsa", "Sfax")}
        assert prix_m2["La Marsa"] > 1.8 * prix_m2["Sfax"]  # règle : 4 000 contre 1 600 TND/m²

    def test_meuble_et_piscine_augmentent_le_prix_selon_les_regles(self):
        base = donnees_demo.prix_selon_regles("Sousse", "villa", "location", 200, False, [], "bon")
        assert donnees_demo.prix_selon_regles("Sousse", "villa", "location", 200, True, [], "bon") == pytest.approx(base * 1.15)
        assert donnees_demo.prix_selon_regles("Sousse", "villa", "location", 200, False, ["piscine"], "bon") == pytest.approx(base * 1.12)


class TestEntrainement:
    """Nettoyage, entraînement, sauvegarde."""

    def test_nettoyage_exclut_les_prix_aberrants(self):
        normale = {"transaction": "vente", "prix": 300000, "surface": 100}
        erreur_saisie = {"transaction": "vente", "prix": 41, "surface": 52}
        assert estimation_prix.filtrer_aberrantes([normale, erreur_saisie]) == ([normale], [erreur_saisie])

    def test_fichiers_et_metadonnees(self, modeles_entraines):
        import json

        assert (modeles_entraines / "prix_location.joblib").exists()
        assert (modeles_entraines / "prix_vente.joblib").exists()
        meta = json.loads((modeles_entraines / "prix_metadonnees.json").read_text(encoding="utf-8"))
        assert set(meta["versions"]) == {"python", "scikit-learn", "numpy", "pandas", "joblib"}
        assert meta["parametres"]["cible"] == "log(prix)"
        for transaction in ("location", "vente"):
            infos = meta["transactions"][transaction]
            assert set(infos["scores_test"]) == {"baseline", "LinearRegression", "RandomForestRegressor"}
            assert infos["modele_retenu"] in ("LinearRegression", "RandomForestRegressor")
            # Le modèle retenu est celui de plus faible MAPE en validation croisée (jamais choisi sur le test).
            assert infos["modele_retenu"] == min(infos["mape_validation_croisee"], key=infos["mape_validation_croisee"].get)
            assert infos["nb_entrainement"] + infos["nb_test"] == infos["nb_annonces"]
            assert set(infos["scores_test"]["baseline"]) == {"mae", "mape", "r2"}

    def test_le_modele_retenu_bat_la_baseline(self, tmp_path):
        # Affirmation centrale : l'IA fait mieux que « prix médian au m² de la ville × surface ».
        meta = estimation_prix.entrainer([en_dict(a) for a in generer_annonces(300)], tmp_path, nb_arbres=20, nb_plis=3)
        for transaction, infos in meta["transactions"].items():
            scores = infos["scores_test"]
            assert scores[infos["modele_retenu"]]["mape"] < scores["baseline"]["mape"], transaction

    def test_donnees_insuffisantes(self, tmp_path):
        annonces = [en_dict(a) for a in generer_annonces(40)]
        with pytest.raises(estimation_prix.DonneesInsuffisantes):
            estimation_prix.entrainer(annonces, tmp_path, nb_arbres=5, nb_plis=2)


class TestPrediction:
    """Prix estimé, fourchette, facteurs, avertissement, temps de réponse."""

    def test_forme_de_la_reponse(self, modeles_entraines):
        resultat = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modeles_entraines)
        assert set(resultat) == {"prix_estime", "fourchette", "devise", "transaction", "confiance", "facteurs",
                                 "modele", "avertissement"}
        assert resultat["confiance"]["niveau"] in ("élevée", "moyenne", "faible") and resultat["confiance"]["raisons"]
        assert resultat["devise"] == "TND" and resultat["transaction"] == "location"
        assert resultat["fourchette"]["min"] <= resultat["prix_estime"] <= resultat["fourchette"]["max"]
        assert resultat["prix_estime"] % 10 == 0  # loyer arrondi à 10 TND
        assert 1 <= len(resultat["facteurs"]) <= 4
        effets = [abs(f["effet_pourcent"]) for f in resultat["facteurs"]]
        assert effets == sorted(effets, reverse=True) and min(effets) >= 1
        assert any(f["libelle"] == "Ville : La Marsa" and f["effet_pourcent"] > 0 for f in resultat["facteurs"])
        assert resultat["avertissement"].startswith("Estimation indicative, calculée sur des données de démonstration.")
        assert set(resultat["modele"]) == {"nom", "mape_test", "entraine_le", "source"}
        assert resultat["modele"]["source"] == "demonstration"  # IA-ANNONCE-PPT-001

    def test_vente_arrondie_au_millier(self, modeles_entraines):
        resultat = estimation_prix.estimer({**ESTIMATION_VALIDE, "transaction": "vente", "type_bien": "villa",
                                            "surface": 300, "caracteristiques": ["piscine"]}, modeles_entraines)
        assert resultat["prix_estime"] % 1000 == 0 and resultat["prix_estime"] > 100000

    def test_ville_inconnue_signalee(self, modeles_entraines):
        # IA-ANNONCE-001-ROBUSTE : la ville inconnue est désormais une raison de confiance faible
        # (avant : une phrase ajoutée à l'avertissement).
        resultat = estimation_prix.estimer({**ESTIMATION_VALIDE, "ville": "Tozeur"}, modeles_entraines)
        assert resultat["confiance"]["niveau"] == "faible"
        assert "Ville « Tozeur » absente des données d'entraînement" in resultat["confiance"]["raisons"]
        assert resultat["avertissement"].startswith("Estimation peu fiable pour ce bien : à utiliser avec prudence.")
        assert not any(f["libelle"].startswith("Ville") for f in resultat["facteurs"])

    def test_ville_insensible_a_la_casse_et_aux_espaces(self, modeles_entraines):
        a = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modeles_entraines)
        b = estimation_prix.estimer({**ESTIMATION_VALIDE, "ville": "  la   MARSA "}, modeles_entraines)
        assert a["prix_estime"] == b["prix_estime"]

    def test_une_piscine_absente_fait_baisser_le_prix(self, modeles_entraines):
        # Effet fort (+12 % dans la règle) : appris de façon fiable. Les petits effets (balcon +2 %) ne le sont
        # pas avec si peu d'annonces : leur signe peut même s'inverser (limite documentée dans le journal).
        resultat = estimation_prix.estimer({**ESTIMATION_VALIDE, "transaction": "vente", "type_bien": "villa",
                                            "surface": 300, "caracteristiques": []}, modeles_entraines)
        sans_piscine = next(f for f in resultat["facteurs"] if f["libelle"] == "Sans piscine")
        assert sans_piscine["effet_pourcent"] < 0

    def test_fourchette_par_les_arbres_quand_la_foret_est_retenue(self, tmp_path, monkeypatch):
        # Forêt seule candidate : la fourchette vient des 10e et 90e centiles des arbres.
        monkeypatch.setattr(estimation_prix, "_candidats", lambda nb_arbres, graine: {
            "RandomForestRegressor": estimation_prix.RandomForestRegressor(n_estimators=nb_arbres, random_state=graine)})
        estimation_prix.entrainer([en_dict(a) for a in generer_annonces(180, graine=3)], tmp_path, nb_arbres=30, nb_plis=3)
        resultat = estimation_prix.estimer(dict(ESTIMATION_VALIDE), tmp_path)
        assert resultat["modele"]["nom"] == "RandomForestRegressor"
        assert resultat["fourchette"]["min"] < resultat["fourchette"]["max"]

    def test_temps_de_reponse_inferieur_a_300_ms_avec_une_foret_de_200_arbres(self, tmp_path, monkeypatch):
        # Pire cas : la forêt complète (200 arbres) et le calcul de la fourchette arbre par arbre.
        monkeypatch.setattr(estimation_prix, "_candidats", lambda nb_arbres, graine: {
            "RandomForestRegressor": estimation_prix.RandomForestRegressor(
                n_estimators=nb_arbres, min_samples_leaf=2, random_state=graine, n_jobs=1)})
        monkeypatch.setattr(estimation_prix, "PERTE_MAX_ELAGAGE", float("-inf"))  # garde la forêt complète
        estimation_prix.entrainer([en_dict(a) for a in generer_annonces(300)], tmp_path, nb_arbres=200, nb_plis=2)
        duree = estimation_prix.mesurer_temps_estimation(dict(ESTIMATION_VALIDE), tmp_path, repetitions=10)
        assert duree < 300, f"{duree:.0f} ms"

    def test_modele_absent(self, tmp_path):
        with pytest.raises(estimation_prix.ModeleIndisponible):
            estimation_prix.estimer(dict(ESTIMATION_VALIDE), tmp_path)


class TestRoute:
    """POST /api/ia/estimation-prix."""

    URL = "/api/ia/estimation-prix"

    def test_reponse_complete(self, client_proprietaire, modele_dans_app):
        reponse = client_proprietaire.post(self.URL, json=ESTIMATION_VALIDE)
        assert reponse.status_code == 200
        donnees = reponse.get_json()
        assert donnees["devise"] == "TND" and donnees["fourchette"]["min"] <= donnees["prix_estime"]

    def test_modele_absent_renvoie_503(self, client_proprietaire):
        reponse = client_proprietaire.post(self.URL, json=ESTIMATION_VALIDE)
        assert reponse.status_code == 503
        assert reponse.get_json() == {
            "error": "modele_indisponible",
            "message": "L'estimation du prix n'est pas encore disponible : le modèle n'a pas été entraîné "
                       "(commande « flask --app run entrainer-prix »).",
        }

    @pytest.mark.parametrize(
        ("champ", "valeur", "message"),
        [
            ("surface", 0, "Doit être supérieur à 0."),
            ("surface", 20000, "Doit être inférieur ou égal à 10000."),
            ("nb_pieces", -1, "Doit être compris entre 0 et 50."),
            ("type_bien", "chateau", "Doit être l'une des valeurs : appartement, maison, studio, villa, residence."),
            ("ville", "", "Doit contenir entre 1 et 100 caractères."),
            ("prix", 1000, "Champ inconnu."),
        ],
    )
    def test_entrees_invalides(self, client_proprietaire, modele_dans_app, champ, valeur, message):
        reponse = client_proprietaire.post(self.URL, json={**ESTIMATION_VALIDE, champ: valeur})
        assert reponse.status_code == 400
        assert message in reponse.get_json()["details"][champ]

    def test_champs_obligatoires(self, client_proprietaire, modele_dans_app):
        reponse = client_proprietaire.post(self.URL, json={})
        assert set(reponse.get_json()["details"]) == {"type_bien", "transaction", "ville", "surface", "nb_pieces"}

    def test_permissions(self, app, client_client, modele_dans_app):
        from tests.outils import ClientNavigateur

        visiteur = ClientNavigateur(app, app.response_class, use_cookies=True)
        assert visiteur.post(self.URL, json=ESTIMATION_VALIDE).status_code == 401
        reponse = client_client.post(self.URL, json=ESTIMATION_VALIDE)
        assert reponse.status_code == 403
        assert reponse.get_json()["message"] == "Espace réservé aux propriétaires."


class TestBadgeMarche:
    """Badge « prix sous / dans / au-dessus du marché » sur le catalogue public."""

    @pytest.fixture
    def annonces_publiques(self, client_proprietaire, annonce_valide):
        """Trois locations publiées à La Marsa (90 m², meublé) : très bon marché, normale, très chère."""
        ids = {}
        for nom, prix in (("sous", 300), ("dans", None), ("dessus", 9000)):
            donnees = {**annonce_valide, "titre": f"Appartement {nom} marché", "ville": "La Marsa", "surface": 90,
                       "nb_pieces": 3, "meuble": True, "caracteristiques": ["climatisation", "balcon"],
                       "prix": prix or 1000}
            annonce = client_proprietaire.post("/api/annonces", json=donnees).get_json()
            client_proprietaire.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
            ids[nom] = annonce["id"]
        return ids

    def test_badge_selon_l_ecart_a_l_estimation(self, client_proprietaire, annonces_publiques, modele_dans_app):
        estime = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_dans_app)["prix_estime"]
        # On fixe le prix « normal » à l'estimation pour qu'il soit dans le marché.
        client_proprietaire.put(f"/api/annonces/{annonces_publiques['dans']}", json={"prix": estime})
        items = {a["id"]: a for a in client_proprietaire.get("/api/annonces").get_json()["items"]}
        sous = items[annonces_publiques["sous"]]["marche"]
        # Badge prudent (IA-ANNONCE-001-ROBUSTE) : « Bonne affaire » sous le bas de la fourchette.
        assert sous["position"] == "sous" and sous["ecart_pourcent"] < -10
        assert sous["libelle"] == "Bonne affaire"
        assert items[annonces_publiques["dans"]]["marche"]["libelle"] == "Prix dans le marché"
        assert items[annonces_publiques["dessus"]]["marche"]["libelle"] == "Prix au-dessus du marché"

    def test_sans_modele_pas_de_badge(self, client_proprietaire, annonces_publiques):
        items = client_proprietaire.get("/api/annonces").get_json()["items"]
        assert all(a["marche"] is None for a in items)

    def test_panne_du_modele_n_empeche_pas_le_catalogue(self, client_proprietaire, annonces_publiques, modele_dans_app, monkeypatch):
        def panne(*args, **kwargs):
            raise RuntimeError("modèle en panne")

        monkeypatch.setattr(estimation_prix, "positions_marche", panne)
        reponse = client_proprietaire.get("/api/annonces")
        assert reponse.status_code == 200
        assert all(a["marche"] is None for a in reponse.get_json()["items"])

    def test_cache_recalcule_seulement_les_annonces_modifiees(self, client_proprietaire, annonces_publiques, modele_dans_app, monkeypatch):
        client_proprietaire.get("/api/annonces")  # remplit le cache
        appels = []
        tableau_reel = estimation_prix.vers_tableau
        monkeypatch.setattr(estimation_prix, "vers_tableau", lambda annonces: appels.append(len(annonces)) or tableau_reel(annonces))
        client_proprietaire.get("/api/annonces")
        assert appels == []  # tout vient du cache
        client_proprietaire.put(f"/api/annonces/{annonces_publiques['sous']}", json={"prix": 350})
        client_proprietaire.get("/api/annonces")
        assert appels == [1]  # seule l'annonce modifiée est recalculée

    def test_badge_sur_la_fiche_publique(self, client_proprietaire, annonces_publiques, modele_dans_app):
        fiche = client_proprietaire.get(f"/api/annonces/{annonces_publiques['sous']}").get_json()
        assert fiche["marche"]["position"] == "sous"


class TestCommandes:
    """flask seed-annonces et flask entrainer-prix."""

    def test_seed_puis_suppression(self, app):
        runner = app.test_cli_runner()
        resultat = runner.invoke(args=["seed-annonces", "--nombre", "50"])
        assert resultat.exit_code == 0, resultat.output
        assert "50 annonces [DÉMO] créées (graine 2026)" in resultat.output
        with app.app_context():
            compte = db.session.query(Utilisateur).filter_by(email=donnees_demo.EMAIL_PROPRIETAIRE_DEMO).one()
            assert compte.role.value == "proprietaire"
            assert (compte.prenom, compte.nom) == ("Agence Démo", "Immobilier")
            assert db.session.query(Annonce).filter_by(owner_id=compte.id).count() == 50
            # Sur la fiche publique, seul le prénom est publié : « Proposé par Agence Démo ».
            annonce = db.session.query(Annonce).filter_by(owner_id=compte.id).first()
            assert annonce.to_dict()["proprietaire"]["prenom"] == "Agence Démo"

        deuxieme = runner.invoke(args=["seed-annonces", "--nombre", "10"])
        assert deuxieme.exit_code == 1
        assert "existent déjà" in deuxieme.output

        suppression = runner.invoke(args=["seed-annonces", "--supprimer"])
        assert "50 annonce(s) [DÉMO] supprimée(s) et compte de démonstration supprimé." in suppression.output
        with app.app_context():
            assert db.session.query(Annonce).count() == 0
            assert db.session.query(Utilisateur).count() == 0

    def test_entrainement_refuse_sans_donnees(self, app):
        resultat = app.test_cli_runner().invoke(args=["entrainer-prix"])
        assert resultat.exit_code == 1
        assert "Données insuffisantes" in resultat.output and "seed-annonces" in resultat.output

    def test_entrainement_affiche_le_tableau(self, app):
        runner = app.test_cli_runner()
        runner.invoke(args=["seed-annonces", "--nombre", "160"])
        resultat = runner.invoke(args=["entrainer-prix", "--arbres", "10", "--plis", "3"])
        assert resultat.exit_code == 0, resultat.output
        for attendu in ("=== LOCATION", "=== VENTE", "MAE (TND)", "baseline", "LinearRegression",
                        "RandomForestRegressor", "<- retenu", "Temps moyen d'une estimation",
                        "QUALITÉ DES DONNÉES", "Doublons exacts exclus : 0", "Séparation vérifiée : 0 identifiant",
                        "MAPE du modèle retenu par ville", "MAPE du modèle retenu par type", "Élagage de la forêt",
                        "Contrôle des équipements",
                        "FICHE_MODELE.md", "pas sur le marché réel"):
            assert attendu in resultat.output
        assert (Path(app.config["MODELES_FOLDER"]) / "prix_metadonnees.json").exists()
        # Console Windows (cp1252) : la sortie complète doit pouvoir s'afficher (la flèche « ← » faisait planter).
        resultat.output.encode("cp1252")


# --- IA-ANNONCE-001-ROBUSTE ------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def modele_reference(tmp_path_factory) -> Path:
    """Modèle entraîné comme en production : les 300 annonces de démonstration de la graine 2026 (celles de
    « seed-annonces »), 5 plis. Forêt de 50 arbres pour la vitesse : le modèle retenu est la régression
    linéaire, qui ne dépend pas du nombre d'arbres (hypothèses vérifiées sur ce modèle avant d'écrire les tests)."""
    dossier = tmp_path_factory.mktemp("modele_reference")
    estimation_prix.entrainer([en_dict(a) for a in generer_annonces(300, graine=2026)], dossier, nb_arbres=50)
    return dossier


def _annonce(**modifs) -> dict:
    """Annonce brute pour les tests de qualité des données."""
    return {"id": None, "titre": "Test", "transaction": "location", "type_bien": "appartement", "ville": "Tunis",
            "surface": 80, "nb_pieces": 3, "meuble": False, "caracteristiques": [], "prix": 800, **modifs}


class TestQualiteDesDonnees:
    """Rapport de qualité avant l'entraînement et étanchéité de la séparation entraînement / test."""

    def test_rapport_exclut_incompletes_aberrantes_et_doublons(self):
        annonces = [
            _annonce(id=1), _annonce(id=2),                              # doublons exacts (ids différents)
            _annonce(id=3, ville="Sousse"),
            _annonce(id=4, prix=None),                                   # prix manquant
            _annonce(id=5, ville="  "),                                  # ville vide
            _annonce(id=6, transaction="vente", prix=41, surface=52),    # 0,79 TND/m² : erreur de saisie
        ]
        utilisables, rapport = estimation_prix.preparer_donnees(annonces)
        assert [a["id"] for a in utilisables] == [1, 3]
        assert rapport["nb_annonces_lues"] == 6 and rapport["nb_annonces_utilisables"] == 2
        assert rapport["valeurs_manquantes"]["prix"] == 1 and rapport["valeurs_manquantes"]["ville"] == 1
        assert rapport["nb_incompletes_exclues"] == 2
        assert rapport["aberrantes"]["nb"] == 1 and rapport["aberrantes"]["exclues"][0]["prix_m2"] == 0.79
        assert "prix au m²" in rapport["aberrantes"]["regle"]
        assert rapport["doublons"]["nb"] == 1
        assert rapport["par_ville"] == {"Tunis": 1, "Sousse": 1} and rapport["par_type"] == {"appartement": 2}
        assert rapport["provenance"] == {"demonstration_generee": 0, "autres": 2}

    def test_une_annonce_dans_l_entrainement_et_le_test_est_refusee(self):
        with pytest.raises(estimation_prix.FuiteDeDonnees):
            estimation_prix.verifier_separation([_annonce(id=1)], [_annonce(id=1, prix=900)])  # même ligne
        with pytest.raises(estimation_prix.FuiteDeDonnees):
            estimation_prix.verifier_separation([_annonce(id=1)], [_annonce(id=2)])            # même contenu
        assert estimation_prix.verifier_separation([_annonce(id=1)], [_annonce(id=2, prix=900)])["contenus_communs"] == 0

    def test_metadonnees_qualite_separation_et_erreurs_par_groupe(self, modele_reference):
        import json

        meta = json.loads((modele_reference / "prix_metadonnees.json").read_text(encoding="utf-8"))
        assert meta["qualite_donnees"]["provenance"]["demonstration_generee"] == 300
        assert sum(meta["qualite_donnees"]["par_transaction"].values()) == meta["qualite_donnees"]["nb_annonces_utilisables"]
        for infos in meta["transactions"].values():
            assert infos["separation"]["identifiants_communs"] == 0 and infos["separation"]["contenus_communs"] == 0
            # Chaque annonce de test est comptée une fois par ville et une fois par type.
            assert sum(g["n"] for g in infos["mape_par_ville"].values()) == infos["nb_test"]
            assert sum(g["n"] for g in infos["mape_par_type"].values()) == infos["nb_test"]
            mapes = [g["mape"] for g in infos["mape_par_ville"].values()]
            assert mapes == sorted(mapes, reverse=True)  # du moins fiable au plus fiable

    def test_entrainement_reproductible(self, tmp_path):
        annonces = [en_dict(a) for a in generer_annonces(180, graine=7)]
        meta_1 = estimation_prix.entrainer(annonces, tmp_path / "a", nb_arbres=10, nb_plis=3)
        meta_2 = estimation_prix.entrainer(annonces, tmp_path / "b", nb_arbres=10, nb_plis=3)
        for transaction in ("location", "vente"):
            un, deux = meta_1["transactions"][transaction], meta_2["transactions"][transaction]
            assert un["scores_test"] == deux["scores_test"] and un["mape_par_ville"] == deux["mape_par_ville"]


class TestElagageEtFiche:
    """Élagage de la forêt et fiche du modèle."""

    def test_elagage_mesure_et_decide_selon_la_regle(self, modele_reference):
        import json

        meta = json.loads((modele_reference / "prix_metadonnees.json").read_text(encoding="utf-8"))
        for infos in meta["transactions"].values():
            elagage = infos["elagage"]
            complete, elaguee = elagage["complete"], elagage["elaguee"]
            assert elaguee["parametres"] == {"n_estimators": 12, "max_depth": 8, "min_samples_leaf": 5}
            assert complete["parametres"]["n_estimators"] == 50 and complete["parametres"]["max_depth"] is None
            # Élaguer réduit réellement le modèle (moins de nœuds, fichier plus petit) et le temps reste < 300 ms.
            assert elaguee["nb_noeuds"] < complete["nb_noeuds"]
            assert elaguee["taille_octets"] < complete["taille_octets"]
            assert complete["temps_ms"] < 300 and elaguee["temps_ms"] < 300
            perte = round(elaguee["mape_validation_croisee"] - complete["mape_validation_croisee"], 2)
            assert elagage["perte_mape_validation_croisee"] == perte
            assert elagage["version_retenue"] == ("elaguee" if perte <= estimation_prix.PERTE_MAX_ELAGAGE else "complete")
            retenue = elagage[elagage["version_retenue"]]
            assert infos["mape_validation_croisee"]["RandomForestRegressor"] == retenue["mape_validation_croisee"]

    def test_version_elaguee_retenue_si_la_perte_est_faible(self, tmp_path, monkeypatch):
        monkeypatch.setattr(estimation_prix, "PERTE_MAX_ELAGAGE", float("inf"))
        meta = estimation_prix.entrainer([en_dict(a) for a in generer_annonces(180, graine=7)], tmp_path,
                                         nb_arbres=8, nb_plis=3)
        assert all(i["elagage"]["version_retenue"] == "elaguee" for i in meta["transactions"].values())

    def test_fiche_du_modele(self, modele_reference):
        fiche = (modele_reference / "FICHE_MODELE.md").read_text(encoding="utf-8")
        for attendu in ("# Fiche du modèle", "données de démonstration générées par des règles",
                        "ne mesurent **pas** la précision d'une estimation sur le marché immobilier réel",
                        "## Données et provenance", "300 annonce(s) de démonstration générée(s)",
                        "## Résultats — location", "## Résultats — vente", "| Ville | n test |", "| Type | n test |",
                        "Élagage de la forêt aléatoire", "## Limites connues", "## Usage prévu",
                        "## Usage déconseillé", "scikit-learn"):
            assert attendu in fiche, attendu

    def test_controle_des_effets_a_contre_sens(self, modele_reference):
        # Même constat que les cas xfail de TestMetamorphiques : le contrôle automatique les retrouve et la
        # fiche les signale.
        modeles = estimation_prix.charger(modele_reference)
        assert estimation_prix.equipements_a_effet_negatif(modeles["location"]) == []
        assert estimation_prix.equipements_a_effet_negatif(modeles["vente"]) == ["climatisation", "ascenseur", "balcon", "jardin"]
        fiche = (modele_reference / "FICHE_MODELE.md").read_text(encoding="utf-8")
        assert "**Effet à contre-sens détecté** : l'ajout de climatisation, ascenseur, balcon, jardin fait BAISSER" in fiche
        assert "Contrôle des équipements : aucun équipement ne fait baisser le prix estimé." in fiche

    def test_ancien_modele_sans_plages_doit_etre_reentraine(self, tmp_path, modeles_entraines):
        import joblib

        shutil.copytree(modeles_entraines, tmp_path, dirs_exist_ok=True)
        ancien = joblib.load(tmp_path / "prix_location.joblib")
        del ancien["plages"]
        joblib.dump(ancien, tmp_path / "prix_location.joblib")
        with pytest.raises(estimation_prix.ModeleIndisponible, match="réentraîné"):
            estimation_prix.estimer(dict(ESTIMATION_VALIDE), tmp_path)


VILLES_DEMO = list(donnees_demo.VILLES)
TYPES = ["appartement", "maison", "studio", "villa", "residence"]


class TestMetamorphiques:
    """Tests métamorphiques : on ne connaît pas le « bon » prix, mais on sait comment il doit (ou ne doit pas)
    changer quand on modifie l'entrée. Chaque hypothèse a été vérifiée sur les données et sur le modèle retenu
    avant d'être écrite ; les cas contredits par le modèle sont marqués xfail et documentés dans le journal."""

    @pytest.mark.parametrize("transaction", ["location", "vente"])
    def test_surface_plus_grande_prix_pas_plus_bas(self, modele_reference, transaction):
        plage = estimation_prix.charger(modele_reference)[transaction]["plages"]["surface"]
        surfaces = [plage[0] + (plage[1] - plage[0]) * k / 5 for k in range(6)]  # dans la plage apprise
        for ville in VILLES_DEMO:
            for type_bien in TYPES:
                prix = [estimation_prix.estimer({**ESTIMATION_VALIDE, "transaction": transaction, "ville": ville,
                                                 "type_bien": type_bien, "surface": s}, modele_reference)["prix_estime"]
                        for s in surfaces]
                assert prix == sorted(prix), (ville, type_bien, list(zip(surfaces, prix)))

    @pytest.mark.parametrize(
        ("transaction", "equipement"),
        [("location", e) for e in estimation_prix.CARACTERISTIQUES]
        + [("vente", e) for e in ("parking", "piscine", "chauffage", "internet")]
        + [pytest.param("vente", e, marks=pytest.mark.xfail(
            strict=True, reason="Hypothèse contredite par le modèle retenu : coefficient appris négatif sur 106 ventes "
                                "d'entraînement (effet faible + confusion dans les données ; voir journal)"))
           for e in ("climatisation", "ascenseur", "balcon", "jardin")],
    )
    def test_ajouter_un_equipement_ne_baisse_pas_le_prix(self, modele_reference, transaction, equipement):
        for ville in VILLES_DEMO:
            for type_bien in TYPES:
                base = {**ESTIMATION_VALIDE, "transaction": transaction, "ville": ville, "type_bien": type_bien,
                        "surface": 120, "caracteristiques": []}
                sans = estimation_prix.estimer(base, modele_reference)["prix_estime"]
                avec = estimation_prix.estimer({**base, "caracteristiques": [equipement]}, modele_reference)["prix_estime"]
                assert avec >= sans, (ville, type_bien, sans, avec)

    def test_meme_entree_meme_resultat(self, modele_reference):
        premiere = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_reference)
        estimation_prix._cache_modeles.clear()  # même après rechargement des fichiers
        assert estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_reference) == premiere

    @pytest.mark.parametrize("ville", ["la marsa", "LA MARSA", "  La   Marsa  ", "La Marsa\t"])
    def test_ville_insensible_a_la_casse_et_aux_espaces_reponse_complete(self, modele_reference, ville):
        reference = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_reference)
        assert estimation_prix.estimer({**ESTIMATION_VALIDE, "ville": ville}, modele_reference) == reference


class TestConfiance:
    """Niveau de confiance de chaque estimation."""

    def test_bien_courant_confiance_elevee(self, modele_reference):
        confiance = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_reference)["confiance"]
        assert confiance["niveau"] == "élevée"
        assert confiance["raisons"][0].startswith("Bien comparable aux annonces d'entraînement")

    def test_exemple_du_cahier_des_charges_ville_inconnue_et_surface_extreme(self, modele_reference):
        resultat = estimation_prix.estimer({**ESTIMATION_VALIDE, "ville": "Tozeur", "surface": 4500}, modele_reference)
        assert resultat["confiance"]["niveau"] == "faible"
        raisons = resultat["confiance"]["raisons"]
        assert raisons[0] == "Ville « Tozeur » absente des données d'entraînement"
        assert raisons[1].startswith("Surface de 4500 m² au-delà de la plage connue (")
        assert resultat["avertissement"].startswith("Estimation peu fiable pour ce bien : à utiliser avec prudence.")

    @pytest.mark.parametrize(("champ", "valeur", "debut"), [
        ("surface", 5, "Surface de 5 m² en deçà de la plage connue"),
        ("surface", 9000, "Surface de 9000 m² au-delà de la plage connue"),
        ("nb_pieces", 40, "40 pièce(s) au-delà de la plage connue"),
    ])
    def test_hors_de_la_plage_apprise(self, modele_reference, champ, valeur, debut):
        confiance = estimation_prix.estimer({**ESTIMATION_VALIDE, champ: valeur}, modele_reference)["confiance"]
        assert confiance["niveau"] == "faible" and confiance["raisons"][0].startswith(debut)

    def test_ville_peu_representee_et_fourchette_large(self, modele_reference):
        modele = dict(estimation_prix.charger(modele_reference)["location"])
        modele["effectifs_villes"] = {**modele["effectifs_villes"], "la marsa": 2}
        confiance = estimation_prix._confiance(dict(ESTIMATION_VALIDE), modele, 1000, 900, 1100)
        assert confiance == {"niveau": "moyenne",
                             "raisons": ["Ville « La Marsa » peu représentée (2 annonce(s) d'entraînement)"]}
        modele = estimation_prix.charger(modele_reference)["location"]
        assert estimation_prix._confiance(dict(ESTIMATION_VALIDE), modele, 1000, 800, 1400)["niveau"] == "moyenne"
        large = estimation_prix._confiance(dict(ESTIMATION_VALIDE), modele, 1000, 500, 1400)
        assert large == {"niveau": "faible", "raisons": ["Fourchette très large : 90 % du prix estimé"]}

    def test_route_renvoie_la_confiance(self, client_proprietaire, modele_dans_app):
        reponse = client_proprietaire.post("/api/ia/estimation-prix", json={**ESTIMATION_VALIDE, "ville": "Tozeur"})
        assert reponse.status_code == 200 and reponse.get_json()["confiance"]["niveau"] == "faible"


class TestBadgePrudent:
    """Badge public : décidé par rapport à la fourchette, absent en confiance faible."""

    def test_position_par_rapport_a_la_fourchette(self):
        assert estimation_prix._position(790, 1000, 800, 1250)["libelle"] == "Bonne affaire"
        assert estimation_prix._position(800, 1000, 800, 1250)["libelle"] == "Prix dans le marché"  # borne incluse
        # -15 % de l'estimation mais dans la fourchette : PAS « bonne affaire » (ancienne règle des ±10 %).
        assert estimation_prix._position(850, 1000, 800, 1250) == {
            "position": "dans", "libelle": "Prix dans le marché", "ecart_pourcent": -15}
        assert estimation_prix._position(1250, 1000, 800, 1250)["libelle"] == "Prix dans le marché"
        assert estimation_prix._position(1260, 1000, 800, 1250) == {
            "position": "au_dessus", "libelle": "Prix au-dessus du marché", "ecart_pourcent": 26}

    @staticmethod
    def _publier(client, annonce_valide, **modifs) -> int:
        donnees = {**annonce_valide, "ville": "La Marsa", "surface": 90, "nb_pieces": 3, "meuble": True,
                   "caracteristiques": ["climatisation", "balcon"], **modifs}
        annonce = client.post("/api/annonces", json=donnees).get_json()
        reponse = client.patch(f"/api/annonces/{annonce['id']}/statut", json={"statut": "publiee"})
        if reponse.status_code == 409 and reponse.get_json().get("error") == "confirmation_requise":
            client.patch(f"/api/annonces/{annonce['id']}/statut",
                         json={"statut": "publiee", "confirmation_fiabilite": True})
        return annonce["id"]

    def test_limites_de_la_fourchette_sur_le_catalogue(self, client_proprietaire, annonce_valide, modele_dans_app):
        fourchette = estimation_prix.estimer(dict(ESTIMATION_VALIDE), modele_dans_app)["fourchette"]
        ids = {nom: self._publier(client_proprietaire, annonce_valide, titre=f"Annonce {nom} fourchette", prix=prix)
               for nom, prix in (("sous", fourchette["min"] - 10), ("bas", fourchette["min"] + 10),
                                 ("haut", fourchette["max"] - 10), ("dessus", fourchette["max"] + 10))}
        items = {a["id"]: a for a in client_proprietaire.get("/api/annonces").get_json()["items"]}
        assert items[ids["sous"]]["marche"]["libelle"] == "Bonne affaire"
        assert items[ids["bas"]]["marche"]["libelle"] == "Prix dans le marché"
        assert items[ids["haut"]]["marche"]["libelle"] == "Prix dans le marché"
        assert items[ids["dessus"]]["marche"]["libelle"] == "Prix au-dessus du marché"

    @pytest.mark.parametrize("modifs", [{"ville": "Tozeur"}, {"surface": 5000}, {"nb_pieces": 45}])
    def test_aucun_badge_si_confiance_faible(self, client_proprietaire, annonce_valide, modele_dans_app, modifs):
        annonce_id = self._publier(client_proprietaire, annonce_valide, titre="Annonce hors plage", prix=100, **modifs)
        # Une caractéristique extrême peut mettre l'annonce en attente; une alerte simple
        # est explicitement confirmée, puis les annonces sans estimation fiable restent sans badge.
        items = {a["id"]: a for a in client_proprietaire.get(
            "/api/annonces?mes_annonces=true"
        ).get_json()["items"]}
        assert items[annonce_id]["statut"] in {"publiee", "en_attente"}
        assert client_proprietaire.get(f"/api/annonces/{annonce_id}").get_json().get("marche") is None
