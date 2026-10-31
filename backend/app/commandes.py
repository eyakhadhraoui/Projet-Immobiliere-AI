"""Commandes Flask en ligne de commande (``flask --app run <commande>``)."""

from __future__ import annotations

import secrets
import json
from collections import Counter
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from marshmallow import ValidationError
from sqlalchemy import select

from app import db
from app.ia import anomalies_annonces, donnees_demo, donnees_ppt, estimation_prix, evaluation_kaggle
from app.models import (ActionHistorique, Annonce, AnnonceControleFiabilite, AnnoncePhoto,
                        RoleUtilisateur, StatutAnnonce, Transaction, TypeBien, Utilisateur)
from app.schemas.utilisateur_schema import valider_mot_de_passe
from app.services.utilisateur_service import creer_compte, normaliser_email
from app.services import securite_connexion_service
from app.services.historique_service import enregistrer_action

EMAIL_DEMO = "proprietaire.demo@example.com"


@click.command("entrainer-anomalies-annonces")
@click.option("--fichier", type=click.Path(path_type=Path), default=None,
              help="CSV Property Prices in Tunisia; par défaut, le CSV à la racine du dépôt.")
@click.option("--graine", default=42, show_default=True, help="Graine de séparation et d'entraînement.")
@with_appcontext
def entrainer_anomalies_annonces(fichier: Path | None, graine: int) -> None:
    """Entraîne IsolationForest et génère un rapport sans inventer de labels."""
    source = fichier or Path(__file__).resolve().parents[2] / "Property Prices in Tunisia.csv"
    try:
        annonces, qualite = donnees_ppt.lire(source)
        resultat = anomalies_annonces.entrainer(annonces, current_app.config["MODELES_FOLDER"], graine=graine)
    except (FileNotFoundError, ValueError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(f"Source : {qualite['nom']} ({qualite['nb_lignes']} lignes; {qualite['nb_annonces_importees']} importées).")
    click.echo(f"Séparation train/validation/test : {resultat['n_train']}/{resultat['n_validation']}/{resultat['n_test']}.")
    click.echo("Pas de labels d'anomalie : précision, rappel et F1 ne sont pas calculés.")
    click.echo(f"Rapport réel : {Path(current_app.config['MODELES_FOLDER']) / anomalies_annonces.FICHIER_RAPPORT}")


@click.command("evaluer-anomalies-annonces")
@click.option("--fichier", required=True, type=click.Path(path_type=Path, exists=True),
              help="CSV indépendant, préparé au format Property Prices in Tunisia.")
@with_appcontext
def evaluer_anomalies_annonces(fichier: Path) -> None:
    """Évalue un modèle existant sur un CSV distinct de celui utilisé pour l'entraînement."""
    try:
        annonces, _ = donnees_ppt.lire(fichier)
        resultat = anomalies_annonces.evaluer(annonces, current_app.config["MODELES_FOLDER"])
    except (FileNotFoundError, ValueError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    dossier = Path(current_app.config["MODELES_FOLDER"])
    rapport = {"source_evaluation": fichier.name, **resultat}
    (dossier / "EVALUATION_ANOMALIES_ANNONCES_TEST.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(f"Échantillon indépendant : {resultat['n_test']} ; alertes : {resultat['alertes']} "
               f"({resultat['taux_alertes']:.1%}).")
    click.echo("Aucun label : ces résultats décrivent la distribution, pas l'exactitude de détection.")
    click.echo(f"Rapport : {dossier / 'EVALUATION_ANOMALIES_ANNONCES_TEST.json'}")


@click.command("evaluer-fiabilite")
@with_appcontext
def evaluer_fiabilite() -> None:
    """Évalue le contrôle de doublons sur validation et test fictifs, sans régler de seuil."""
    from app.ia.fiabilite.evaluation import evaluer_jeu

    base = Path(__file__).resolve().parents[1]
    jeu = base / "tests" / "donnees_fiabilite" / "jeu_annote.json"
    try:
        rapport = evaluer_jeu(jeu, current_app.config["MODELES_FOLDER"])
    except (OSError, ValueError, KeyError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    seuils_path = Path(current_app.config["MODELES_FOLDER"]) / "fiabilite" / "seuils.json"
    seuils_config = json.loads(seuils_path.read_text(encoding="utf-8")) if seuils_path.exists() else {}
    decision_production = seuils_config.get("decision_production")
    for ensemble in ("validation", "test"):
        mesures = rapport[ensemble]["comparaison_texte_et_photos"]
        click.echo(f"{ensemble}: {mesures['paires']} paires; précision {mesures['precision']:.3f}; "
                   f"rappel {mesures['rappel']:.3f}; F1 {mesures['f1']:.3f}; "
                   f"faux positifs {mesures['taux_faux_positifs']:.3f}.")
    if decision_production:
        click.echo(f"Décision de production protégée : {decision_production.get('modele')} "
                   f"(seuil {decision_production.get('seuil')}); aucun seuil n'a été modifié.")
    click.echo("Labels prix/surface absents du jeu: aucune métrique supervisée d'anomalie calculée.")
    click.echo(f"Rapport: {Path(current_app.config['MODELES_FOLDER']) / 'fiabilite' / 'rapport_evaluation.json'}")


@click.command("evaluer-test-externe")
@click.option("--verifier-seulement", is_flag=True,
              help="Valide le format et les étiquettes sans calculer les similarités.")
@with_appcontext
def evaluer_test_externe(verifier_seulement: bool) -> None:
    """Évalue les paires externes en lecture seule, sans modifier le choix de production."""
    from app.ia.fiabilite.externe import JeuExterneInvalide, charger_paires, evaluer_test_externe as evaluer

    racine = Path(__file__).resolve().parents[2]
    chemin = racine / "docs" / "test-externe-paraphrases.txt"
    try:
        paires = charger_paires(chemin)
    except (OSError, JeuExterneInvalide) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(f"Format valide : {len(paires)} paires, {sum(p['doublon'] for p in paires)} DOUBLON, "
               f"{sum(not p['doublon'] for p in paires)} DIFFERENT, "
               f"{sum(p['humain'] for p in paires)} réécrite(s) à la main.")
    if verifier_seulement:
        return
    try:
        rapport = evaluer(chemin, current_app.config["MODELES_FOLDER"])
    except (OSError, ValueError, KeyError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    sortie = Path(current_app.config["MODELES_FOLDER"]) / "fiabilite" / "rapport_test_externe.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    for nom, mesures in rapport["resultats"].items():
        click.echo(f"{nom}: F1 {mesures['f1']:.3f}, faux positifs {mesures['fp']}, "
                   f"IC95 F1 [{mesures['ic95_f1'][0]:.3f}; {mesures['ic95_f1'][1]:.3f}].")
    click.echo(rapport["recommandation"])
    click.echo(f"Seuils inchangés; rapport : {sortie}")


@click.command("installer-modele-fiabilite")
@with_appcontext
def installer_modele_fiabilite() -> None:
    """Télécharge une fois la révision épinglée MiniLM; l'application reste hors ligne ensuite."""
    from app.ia.fiabilite.texte import ModeleTexteIndisponible, telecharger_modele_base

    try:
        chemin = telecharger_modele_base(current_app.config["MODELES_FOLDER"])
    except (OSError, ModeleTexteIndisponible, RuntimeError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(f"Modèle local installé: {chemin}")


@click.command("rapport-fiabilite")
@with_appcontext
def rapport_fiabilite() -> None:
    """Affiche à l'opératrice les annonces en attente et les demandes de revue."""
    annonces = db.session.scalars(
        select(Annonce).where(Annonce.statut == StatutAnnonce.EN_ATTENTE,
                             Annonce.motif_attente == "fiabilite")
        .order_by(Annonce.revue_demandee_le.desc().nullslast(), Annonce.updated_at.asc())
    ).all()
    if not annonces:
        click.echo("Aucune annonce en attente de vérification.")
        return
    for annonce in annonces:
        controle = db.session.scalar(select(AnnonceControleFiabilite).where(
            AnnonceControleFiabilite.annonce_id == annonce.id
        ))
        click.echo(f"ID {annonce.id} | propriétaire {annonce.owner_id} | {annonce.titre} | "
                   f"revue demandée: {annonce.revue_demandee_le or 'non'}")
        if controle:
            click.echo(f"  niveau={controle.niveau}; score={controle.score}; raisons={controle.raisons}")
            for doublon in controle.doublons or []:
                click.echo(f"  annonce liée {doublon.get('annonce_id')}: {doublon.get('signaux')}")


@click.command("moderer-annonce")
@click.option("--id", "annonce_id", required=True, type=int)
@click.option("--decision", required=True, type=click.Choice(["publier", "refuser"], case_sensitive=False))
@click.option("--motif", required=True, type=str, help="Motif de la décision (500 caractères maximum).")
@with_appcontext
def moderer_annonce(annonce_id: int, decision: str, motif: str) -> None:
    """Publie ou renvoie en brouillon une annonce après revue humaine."""
    annonce = db.session.get(Annonce, annonce_id)
    if annonce is None:
        raise click.ClickException("Annonce introuvable.")
    if annonce.statut != StatutAnnonce.EN_ATTENTE or annonce.motif_attente != "fiabilite":
        raise click.ClickException("Cette annonce n'est pas en attente de vérification.")
    motif = motif.strip()
    if not motif or len(motif) > 500:
        raise click.ClickException("Le motif doit contenir entre 1 et 500 caractères.")
    controle = db.session.scalar(select(AnnonceControleFiabilite).where(
        AnnonceControleFiabilite.annonce_id == annonce.id
    ))
    if decision.lower() == "publier":
        from app.ia.fiabilite.service import identifiants_photos_en_cause

        photo_ids = identifiants_photos_en_cause(
            annonce, controle, Path(current_app.config["MODELES_FOLDER"])
        )
        if photo_ids:
            raise click.ClickException(
                "Publication bloquée : retirez les photos déjà utilisées dans une autre annonce, "
                "puis relancez le contrôle."
            )
        annonce.statut = StatutAnnonce.PUBLIEE
        annonce.motif_attente = None
        action = "publier"
    else:
        photo_ids = {pair["photo_id_a"] for doublon in (controle.doublons if controle else [])
                     for pair in doublon.get("paires_photos", []) if pair.get("photo_id_a")}
        empreintes = list(annonce.empreintes_refusees or [])
        photos_refusees = (db.session.scalars(select(AnnoncePhoto).where(AnnoncePhoto.id.in_(photo_ids))).all()
                           if photo_ids else [])
        for photo in photos_refusees:
            valeur = {"sha256": photo.sha256, "phash": photo.phash}
            if valeur not in empreintes and (photo.sha256 or photo.phash):
                empreintes.append(valeur)
        annonce.empreintes_refusees = empreintes
        annonce.statut = StatutAnnonce.BROUILLON
        annonce.motif_attente = None
        action = "refuser"
    enregistrer_action(annonce, ActionHistorique.DECISION_MODERATION,
                       {"decision": action, "motif": motif})
    db.session.commit()
    click.echo(f"Annonce {annonce.id}: décision {action} enregistrée; statut {annonce.statut.value}.")


@click.command("entrainer-connexions")
@with_appcontext
def entrainer_connexions() -> None:
    """Entraîne IsolationForest à partir des événements de connexion enregistrés."""
    try:
        resultat = securite_connexion_service.entrainer(current_app.config["MODELES_FOLDER"])
    except ValueError as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(f"Événements : {resultat['evenements']} ; anomalies d'apprentissage : {resultat['anomalies_apprentissage']}.")


@click.command("evaluer-connexions")
@with_appcontext
def evaluer_connexions() -> None:
    """Compare les anomalies IsolationForest aux alertes déclenchées par les règles."""
    try:
        resultat = securite_connexion_service.evaluer()
    except ValueError as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(
        f"Événements évalués : {resultat['evenements_evalues']} ; "
        f"anomalies IsolationForest : {resultat['anomalies_isolation_forest']} ; "
        f"alertes par règles : {resultat['alertes_regles']}."
    )


@click.command("nettoyer-connexions")
@with_appcontext
def nettoyer_connexions() -> None:
    """Supprime les événements de sécurité au-delà de la durée de conservation."""
    retention = int(current_app.config["CONNEXION_RETENTION_JOURS"])
    nombre = securite_connexion_service.nettoyer(retention)
    click.echo(f"{nombre} événement(s) supprimé(s); conservation configurée : {retention} jours.")


@click.command("seed-utilisateurs")
@click.option("--email", default=EMAIL_DEMO, show_default=True, help="Email du propriétaire de démonstration.")
@with_appcontext
def seed_utilisateurs(email: str) -> None:
    """Crée un propriétaire de démonstration ; le mot de passe est demandé au clavier (jamais écrit dans le code).

    Args:
        email: Email du compte à créer.

    Raises:
        click.ClickException: Si le mot de passe ne respecte pas la politique de sécurité.
    """
    email = normaliser_email(email)
    if db.session.scalar(select(Utilisateur.id).where(Utilisateur.email == email)) is not None:
        click.echo(f"Un compte existe déjà avec l'email {email} : rien n'a été créé.")
        return

    mot_de_passe = click.prompt("Mot de passe", hide_input=True, confirmation_prompt="Confirmez le mot de passe")
    try:
        valider_mot_de_passe(mot_de_passe)
    except ValidationError as erreur:
        raise click.ClickException("Mot de passe refusé : " + " ".join(erreur.messages)) from erreur

    utilisateur = creer_compte({
        "nom": "Démo",
        "prenom": "Propriétaire",
        "email": email,
        "mot_de_passe": mot_de_passe,
        "role": RoleUtilisateur.PROPRIETAIRE,
        "ville": "Tunis",
    })
    click.echo(f"Propriétaire de démonstration créé : {utilisateur.email} (id {utilisateur.id}).")


# --- IA-ANNONCE-001 : données de démonstration et entraînement de l'estimation du prix --------------------------

def _compte_demo(creer: bool) -> Utilisateur | None:
    """Compte propriétaire dédié aux annonces de démonstration.

    Son mot de passe est aléatoire, jamais affiché ni enregistré en clair : personne ne peut s'y connecter.
    Il sert uniquement à porter les annonces « [DÉMO] ».

    Args:
        creer: Créer le compte s'il n'existe pas.

    Returns:
        Utilisateur | None: Le compte, ou ``None`` s'il n'existe pas et ``creer`` est faux.
    """
    compte = db.session.scalar(select(Utilisateur).where(Utilisateur.email == donnees_demo.EMAIL_PROPRIETAIRE_DEMO))
    if compte is None and creer:
        compte = Utilisateur(nom=donnees_demo.NOM_PROPRIETAIRE_DEMO, prenom=donnees_demo.PRENOM_PROPRIETAIRE_DEMO,
                             email=donnees_demo.EMAIL_PROPRIETAIRE_DEMO,
                             role=RoleUtilisateur.PROPRIETAIRE, ville="Tunis")
        compte.definir_mot_de_passe(secrets.token_urlsafe(32))
        db.session.add(compte)
        db.session.flush()
    return compte


def _annonces_demo(compte: Utilisateur) -> list[Annonce]:
    """Annonces de démonstration du compte dédié (titre commençant par « [DÉMO] »)."""
    return db.session.scalars(
        select(Annonce).where(Annonce.owner_id == compte.id, Annonce.titre.startswith(donnees_demo.PREFIXE_TITRE))
    ).all()


@click.command("seed-annonces")
@click.option("--nombre", default=300, show_default=True, type=click.IntRange(1, 5000), help="Nombre d'annonces.")
@click.option("--graine", default=donnees_demo.GRAINE_PAR_DEFAUT, show_default=True, help="Graine aléatoire.")
@click.option("--supprimer", is_flag=True, help="Supprime les annonces [DÉMO] (et le compte de démonstration).")
@with_appcontext
def seed_annonces(nombre: int, graine: int, supprimer: bool) -> None:
    """Génère (ou supprime) des annonces de démonstration « [DÉMO] » pour entraîner l'estimation du prix.

    Les règles de prix sont documentées dans ``app/ia/donnees_demo.py``. Ces annonces n'ont pas d'entrée
    d'historique : ce ne sont pas des actions d'un utilisateur.

    Args:
        nombre: Nombre d'annonces à générer.
        graine: Graine aléatoire (mêmes annonces à chaque exécution).
        supprimer: Supprimer au lieu de générer.

    Raises:
        click.ClickException: Si des annonces de démonstration existent déjà.
    """
    if supprimer:
        compte = _compte_demo(creer=False)
        if compte is None:
            click.echo("Aucune annonce de démonstration à supprimer.")
            return
        annonces = _annonces_demo(compte)
        for annonce in annonces:
            db.session.delete(annonce)
        db.session.flush()
        restantes = db.session.scalar(select(Annonce.id).where(Annonce.owner_id == compte.id).limit(1))
        if restantes is None:
            db.session.delete(compte)
        db.session.commit()
        click.echo(f"{len(annonces)} annonce(s) [DÉMO] supprimée(s)" + (" et compte de démonstration supprimé." if restantes is None else "."))
        return

    compte = _compte_demo(creer=True)
    existantes = _annonces_demo(compte)
    if existantes:
        raise click.ClickException(
            f"{len(existantes)} annonce(s) [DÉMO] existent déjà. Lancez d'abord : flask --app run seed-annonces --supprimer"
        )
    generees = donnees_demo.generer_annonces(nombre, graine)
    db.session.add_all(Annonce(**donnees_demo.en_dict(a), owner_id=compte.id) for a in generees)
    db.session.commit()
    statuts = Counter(a.statut for a in generees)
    transactions = Counter(a.transaction for a in generees)
    click.echo(f"{len(generees)} annonces [DÉMO] créées (graine {graine}) pour {compte.email} (id {compte.id}).")
    click.echo(f"  transactions : {dict(transactions)} | statuts : {dict(statuts)}")
    click.echo(f"  villes : {dict(Counter(a.ville for a in generees).most_common())}")


@click.command("entrainer-prix")
@click.option("--arbres", default=estimation_prix.NB_ARBRES, show_default=True, help="Nombre d'arbres de la forêt.")
@click.option("--graine", default=estimation_prix.GRAINE, show_default=True, help="Graine aléatoire.")
@click.option("--plis", default=estimation_prix.NB_PLIS, show_default=True, help="Plis de la validation croisée.")
@click.option("--source", type=click.Choice(["base", "ppt"]), default="base", show_default=True,
              help="base : annonces de la base (démonstration) ; ppt : CSV « Property Prices in Tunisia ».")
@click.option("--fichier", type=click.Path(path_type=Path), default=None,
              help="CSV « Property Prices in Tunisia » (obligatoire avec --source ppt).")
@click.option("--licence", default="non vérifiée", show_default=True,
              help="Licence du jeu de données, recopiée dans la fiche du modèle (--source ppt).")
@with_appcontext
def entrainer_prix(arbres: int, graine: int, plis: int, source: str, fichier: Path | None, licence: str) -> None:
    """Entraîne l'estimation du prix et affiche le tableau d'évaluation.

    Avec ``--source ppt`` (IA-ANNONCE-PPT-001), le modèle est entraîné sur les annonces réelles du CSV ; les annonces
    de la base (démonstration) servent seulement aux effets du meublé et des équipements, et l'ancien modèle est
    comparé au nouveau sur les mêmes annonces de test.

    Args:
        arbres: Nombre d'arbres de la forêt aléatoire.
        graine: Graine aléatoire.
        plis: Nombre de plis de la validation croisée.
        source: ``base`` ou ``ppt``.
        fichier: CSV des annonces réelles.
        licence: Licence déclarée du jeu de données.

    Raises:
        click.ClickException: S'il n'y a pas assez d'annonces ou si le fichier est absent ou invalide.
    """
    # Rappel : toute la sortie de cette commande doit rester affichable par la console Windows (cp1252) :
    # pas de flèches ni de symboles mathématiques Unicode (test : test_entrainement_affiche_le_tableau).
    annonces = [
        {"id": a.id, "titre": a.titre, "type_bien": a.type_bien.value, "transaction": a.transaction.value,
         "ville": a.ville, "surface": a.surface,
         "nb_pieces": a.nb_pieces, "meuble": a.meuble, "caracteristiques": a.caracteristiques, "prix": a.prix}
        for a in db.session.scalars(select(Annonce))
    ]
    dossier = Path(current_app.config["MODELES_FOLDER"])
    options: dict = {}
    if source == "ppt":
        if fichier is None:
            raise click.ClickException("--fichier est obligatoire avec --source ppt.")
        try:
            reelles, import_ppt = donnees_ppt.lire(fichier)
        except (FileNotFoundError, ValueError) as erreur:
            raise click.ClickException(str(erreur)) from erreur
        try:
            modeles_avant = estimation_prix.charger(dossier)
        except estimation_prix.ModeleIndisponible:
            modeles_avant = None
        options = {"source": {**import_ppt, "licence": licence},
                   "ajustements": estimation_prix.ajustements_demo(annonces), "modeles_avant": modeles_avant}
        click.echo(f"Source : {import_ppt['nom']} ({import_ppt['fichier']}, {import_ppt['nb_lignes']} lignes) | "
                   f"licence : {licence}")
        click.echo(f"Annonces importées : {import_ppt['nb_annonces_importees']} | écartées à l'import : "
                   f"{import_ppt['ecartees']}")
        click.echo(f"Effets du meublé et des équipements repris de {len(annonces)} annonces de la base (démonstration)")
        annonces = reelles
    click.echo(f"Entraînement sur {len(annonces)} annonces…")
    try:
        meta = estimation_prix.entrainer(annonces, dossier, nb_arbres=arbres, graine=graine, nb_plis=plis, **options)
    except estimation_prix.DonneesInsuffisantes as erreur:
        raise click.ClickException(
            f"Données insuffisantes ({erreur}) Générez des données : flask --app run seed-annonces --nombre 300"
        ) from erreur

    qualite = meta["qualite_donnees"]
    click.echo("")
    click.echo("=== QUALITÉ DES DONNÉES (avant entraînement) ===")
    click.echo(f"Annonces lues : {qualite['nb_annonces_lues']} | utilisables : {qualite['nb_annonces_utilisables']} "
               f"| provenance : {qualite['provenance']['demonstration_generee']} démonstration générée, "
               f"{qualite['provenance']['autres']} autre(s)")
    click.echo(f"Valeurs manquantes : {qualite['valeurs_manquantes']} | incomplètes exclues : "
               f"{qualite['nb_incompletes_exclues']}")
    click.echo(f"Prix aberrants exclus : {qualite['aberrantes']['nb']} (règle : {qualite['aberrantes']['regle']})")
    exclues = qualite["aberrantes"]["exclues"]
    for exclue in exclues[:estimation_prix.MAX_EXCLUES_AFFICHEES]:
        click.echo(f"  - {exclue['titre']} ({exclue['transaction']}, {exclue['prix_m2']} TND/m²)")
    if len(exclues) > estimation_prix.MAX_EXCLUES_AFFICHEES:
        click.echo(f"  - ... et {len(exclues) - estimation_prix.MAX_EXCLUES_AFFICHEES} autre(s) (voir les métadonnées)")
    click.echo(f"Doublons exacts exclus : {qualite['doublons']['nb']}")
    click.echo(f"Par transaction : {qualite['par_transaction']}")
    click.echo(f"Par ville : {qualite['par_ville']}")
    click.echo(f"Par type : {qualite['par_type']}")
    for transaction, infos in meta["transactions"].items():
        click.echo("")
        click.echo(f"=== {transaction.upper()} : {infos['nb_annonces']} annonces "
                   f"({infos['nb_entrainement']} entraînement / {infos['nb_test']} test) ===")
        sep = infos["separation"]
        click.echo(f"Séparation vérifiée : {sep['identifiants_communs']} identifiant et {sep['contenus_communs']} "
                   "contenu communs entre entraînement et test")
        click.echo(f"{'Modèle':<24}{'MAE (TND)':>14}{'MAPE (%)':>11}{'R²':>8}{'MAPE val. croisée (%)':>24}")
        for nom, scores in infos["scores_test"].items():
            cv = infos["mape_validation_croisee"].get(nom)
            # « <- » et non « ← » : la console Windows (cp1252) ne sait pas afficher la flèche Unicode
            # et la commande plantait (UnicodeEncodeError) après avoir écrit les modèles.
            retenu = "  <- retenu" if nom == infos["modele_retenu"] else ""
            click.echo(f"{nom:<24}{scores['mae']:>14,.0f}{scores['mape']:>11.1f}{scores['r2']:>8.3f}"
                       f"{(f'{cv:.1f}' if cv is not None else '—'):>24}{retenu}".replace(",", " "))
        for titre, groupes in (("ville", infos["mape_par_ville"]), ("type", infos["mape_par_type"])):
            click.echo(f"MAPE du modèle retenu par {titre} (test, du moins fiable au plus fiable) :")
            for nom, valeurs in groupes.items():
                click.echo(f"  {nom:<14} n={valeurs['n']:<3} MAPE {valeurs['mape']:>5.1f} % "
                           f"(baseline {valeurs['mape_baseline']:.1f} %)")
        elagage = infos["elagage"]
        if elagage:
            click.echo("Élagage de la forêt :")
            click.echo(f"  {'Version':<10}{'Noeuds':>8}{'Fichier (Ko)':>14}{'Temps méd. (ms)':>17}"
                       f"{'MAPE CV (%)':>13}{'MAPE test (%)':>15}")
            for version in ("complete", "elaguee"):
                v = elagage[version]
                click.echo(f"  {version:<10}{v['nb_noeuds']:>8}{v['taille_octets'] / 1024:>14.1f}{v['temps_ms']:>17.1f}"
                           f"{v['mape_validation_croisee']:>13.1f}{v['scores_test']['mape']:>15.1f}")
            click.echo(f"  Retenue : {elagage['version_retenue']} (écart de MAPE CV : "
                       f"{elagage['perte_mape_validation_croisee']:+.2f} point ; {elagage['regle']})")
        negatifs = infos["equipements_a_effet_negatif"]
        click.echo("Contrôle des équipements : " + (f"ATTENTION, l'ajout de {', '.join(negatifs)} fait baisser le "
                                                     "prix estimé (effet faible mal appris)" if negatifs
                                                     else "aucun équipement ne fait baisser le prix estimé"))
        comparaison = infos["comparaison_avant_apres"]
        if comparaison:
            click.echo(f"Avant / après sur les mêmes {comparaison['nb_test']} annonces de test :")
            for etape, c in (("avant", comparaison["avant"]), ("après", comparaison["apres"]),
                             ("baseline", comparaison["baseline"])):
                nom = f"{c['nom']} ({c['source']})" if "nom" in c else "prix médian au m2 de la ville"
                click.echo(f"  {etape:<9}{nom:<44} MAE {c['mae']:>12,.0f} TND | MAPE {c['mape']:>6.1f} % | "
                           f"R2 {c['r2']:>7.3f}".replace(",", " "))
        ajust = infos["ajustements_demo"]
        if ajust:
            click.echo("Effets repris de la démonstration (%) : " + ", ".join(
                f"{col} {v:+.1f}" for col, v in ajust["effets_pourcent"].items())
                + (f" | mis à 0 (signe contraire aux règles) : {', '.join(ajust['mis_a_zero'])}"
                   if ajust["mis_a_zero"] else ""))
        exemple = next(a for a in annonces if a["transaction"] == transaction)
        duree = estimation_prix.mesurer_temps_estimation(exemple, dossier)
        click.echo(f"Temps moyen d'une estimation (prix + fourchette + confiance + facteurs) : {duree:.1f} ms")
    click.echo("")
    click.echo(f"Modèles enregistrés dans {dossier} (prix_location.joblib, prix_vente.joblib, "
               f"{estimation_prix.FICHIER_METADONNEES}, {estimation_prix.FICHIER_FICHE}).")
    if source == "ppt":
        click.echo("Rappel : scores mesurés sur des prix AFFICHÉS d'annonces réelles (pas des prix de vente conclus) ; "
                   f"licence du jeu de données : {licence}.")
    else:
        click.echo("Rappel : scores mesurés sur des données de démonstration générées, pas sur le marché réel.")


# --- IA-ANNONCE-002-KAGGLE : comparaison avant / après sur des ventes réelles ---------------------------------

@click.command("evaluer-kaggle")
@click.option("--fichier", required=True, type=click.Path(path_type=Path),
              help="train.csv de la compétition Kaggle, ou l'archive .zip téléchargée qui le contient.")
@click.option("--classement", type=click.Path(path_type=Path), default=None,
              help="CSV du classement privé Kaggle (facultatif ; seuls rangs et scores sont lus).")
@click.option("--arbres", default=estimation_prix.NB_ARBRES, show_default=True, help="Nombre d'arbres des forêts.")
@click.option("--graine", default=estimation_prix.GRAINE, show_default=True, help="Graine aléatoire.")
@click.option("--plis", default=estimation_prix.NB_PLIS, show_default=True, help="Plis de la validation croisée.")
@with_appcontext
def evaluer_kaggle(fichier: Path, classement: Path | None, arbres: int, graine: int, plis: int) -> None:
    """Compare le système d'estimation existant à des améliorations, sur des ventes réelles (Kaggle).

    Ne modifie ni la base ni les modèles de l'application : résultats dans MODELES_FOLDER/kaggle/.

    Args:
        fichier: train.csv ou archive Kaggle.
        classement: CSV du classement privé (repère indicatif).
        arbres: Nombre d'arbres des forêts.
        graine: Graine aléatoire.
        plis: Nombre de plis de la validation croisée.

    Raises:
        click.ClickException: Si le fichier est absent ou n'a pas le format attendu.
    """
    dossier = Path(current_app.config["MODELES_FOLDER"])
    try:
        r = evaluation_kaggle.evaluer(fichier, dossier, nb_arbres=arbres, graine=graine, nb_plis=plis,
                                      chemin_classement=classement)
    except evaluation_kaggle.FichierKaggleInvalide as erreur:
        raise click.ClickException(str(erreur)) from erreur

    q = r["qualite_donnees"]
    click.echo(f"Source : {r['source']['fichier']} ({r['source']['lignes']} ventes, "
               f"{r['source']['doublons_exacts_bruts_hors_id']} doublons exacts bruts)")
    click.echo(f"Contrôle qualité : {q['nb_annonces_utilisables']} utilisables | incomplètes {q['nb_incompletes_exclues']} "
               f"| aberrantes {q['aberrantes']['nb']} | doublons {q['doublons']['nb']}")
    click.echo(f"Valeurs manquantes : {q['valeurs_manquantes']}")
    s = r["separation"]
    click.echo(f"Séparation : {s['nb_entrainement']} entraînement / {s['nb_test']} test, "
               f"{s['identifiants_communs']} identifiant et {s['contenus_communs']} contenu communs")
    click.echo("")
    click.echo(f"{'Modèle':<52}{'MAE (TND)':>12}{'MAPE (%)':>10}{'R²':>8}{'RMSE (TND)':>13}{'MAPE CV (%)':>13}")
    for nom, ligne in r["modeles"].items():
        t = ligne["test"]
        cv = "-" if ligne["cv"] is None else f"{ligne['cv']:.1f}"
        click.echo(f"{nom[:51]:<52}{t['mae']:>12,.0f}{t['mape']:>10.1f}{t['r2']:>8.3f}{t['rmse']:>13,.0f}{cv:>13}"
                   .replace(",", " ") + ("  <- retenu" if ligne.get("retenu") else ""))
    click.echo("")
    click.echo("MAPE par gouvernorat (test) : avant -> après")
    apres = r["mape_par_gouvernorat"]["apres"]
    for g, v in r["mape_par_gouvernorat"]["avant"].items():
        click.echo(f"  {g:<14} n={v['n']:<4} {v['mape']:>6.1f} % -> {apres[g]['mape']:>6.1f} %")
    if "classement_kaggle" in r:
        c = r["classement_kaggle"]
        click.echo("")
        milliers = lambda v: f"{v:,.0f}".replace(",", " ")  # noqa: E731 — 450603 → « 450 603 »
        click.echo(f"Repère indicatif, classement privé Kaggle ({c['nb_equipes']} équipes, autres annonces de test) : "
                   f"meilleur {milliers(c['meilleur'])}, médiane {milliers(c['median'])}, dernier {milliers(c['dernier'])}")
    click.echo("")
    click.echo(f"Rapport : {dossier / evaluation_kaggle.DOSSIER_RESULTATS / 'EVALUATION_KAGGLE.md'} "
               "(l'estimation de l'application n'est pas modifiée).")


def generer_photos_demo(dossier: Path) -> dict[str, Path]:
    """Génère 4 photos synthétiques avec formes géométriques et graine 2026, plus la photo 1 en miroir."""
    import random
    from PIL import Image, ImageDraw

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2026)

    palettes = [
        ((235, 240, 255), [((30, 40, 160, 150), (70, 110, 200)), ((180, 70, 290, 190), (220, 130, 60))]),
        ((255, 245, 235), [((40, 30, 170, 160), (200, 70, 70)), ((190, 60, 300, 200), (60, 160, 80))]),
        ((240, 255, 240), [((30, 50, 150, 170), (140, 80, 180)), ((170, 40, 280, 180), (200, 180, 40))]),
        ((250, 250, 250), [((50, 30, 190, 150), (80, 150, 220)), ((160, 80, 290, 200), (210, 90, 130))]),
    ]

    photos: dict[str, Path] = {}
    for i, (fond, formes) in enumerate(palettes, start=1):
        image = Image.new("RGB", (320, 240), fond)
        draw = ImageDraw.Draw(image)
        for (x0, y0, x1, y1), couleur in formes:
            draw.rectangle([x0, y0, x1, y1], fill=couleur)
        chemin = dossier / f"photo{i}.jpg"
        image.save(chemin, "JPEG", quality=90)
        photos[f"photo{i}"] = chemin

    # Photo 1 en miroir
    with Image.open(photos["photo1"]) as img1:
        miroir = img1.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        chemin_miroir = dossier / "photo1_miroir.jpg"
        miroir.save(chemin_miroir, "JPEG", quality=90)
        photos["photo1_miroir"] = chemin_miroir

    return photos


@click.command("preparer-demo")
@click.option("--base", required=True, type=click.Path(path_type=Path),
              help="Chemin vers la base de données SQLite cible.")
@click.option("--uploads", type=click.Path(path_type=Path), default=None,
              help="Dossier des uploads pour les photos d'annonces.")
@click.option("--photos-demo", type=click.Path(path_type=Path), default=None,
              help="Dossier où générer les photos de démonstration.")
@click.option("--confirmer", is_flag=True, default=False,
              help="Confirme la modification de la base principale de l'application.")
@with_appcontext
def preparer_demo(base: Path, uploads: Path | None, photos_demo: Path | None, confirmer: bool) -> None:
    """Prépare les comptes et annonces de démonstration pour le test de fiabilité."""
    import os
    import shutil
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.ia.fiabilite.empreintes import empreintes_image

    base_path = Path(base).resolve()
    if not base_path.is_file():
        raise click.ClickException(f"Base SQLite introuvable : {base}")

    db_principale = (Path(current_app.instance_path) / "immobilier.db").resolve()
    if base_path == db_principale and not confirmer:
        raise click.ClickException("Refus de modifier la base principale sans --confirmer.")

    mot_de_passe = os.environ.get("DEMO_MOT_DE_PASSE")
    if not mot_de_passe:
        mot_de_passe = click.prompt("Mot de passe des comptes de démonstration",
                                    hide_input=True, confirmation_prompt="Confirmez le mot de passe")
    try:
        valider_mot_de_passe(mot_de_passe)
    except ValidationError as err:
        raise click.ClickException("Mot de passe refusé : " + " ".join(err.messages)) from err

    dossier_photos = photos_demo or (Path(current_app.instance_path) / "demo-photos")
    photos = generer_photos_demo(Path(dossier_photos))

    dossier_uploads = uploads or Path(current_app.config["UPLOAD_FOLDER"])
    Path(dossier_uploads).mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{base_path}")
    with Session(engine) as session:
        comptes_infos = [
            ("amira@test.tn", "Amira", "Ben Salem", "Nabeul"),
            ("sami@test.tn", "Sami", "Trabelsi", "Sousse"),
            ("karim@test.tn", "Karim", "Gharbi", "Tunis"),
        ]
        comptes = {}
        for email, prenom, nom, ville in comptes_infos:
            u = session.scalar(select(Utilisateur).where(Utilisateur.email == email))
            if u is None:
                u = Utilisateur(nom=nom, prenom=prenom, email=email,
                                role=RoleUtilisateur.PROPRIETAIRE, ville=ville)
                u.definir_mot_de_passe(mot_de_passe)
                session.add(u)
                session.flush()
            else:
                u.definir_mot_de_passe(mot_de_passe)
            comptes[email] = u

        amira = comptes["amira@test.tn"]

        # 1. Annonce studio de Sousse pour Amira
        titre1 = "Studio meublé pour étudiant près de la faculté"
        a1 = session.scalar(select(Annonce).where(Annonce.owner_id == amira.id, Annonce.titre == titre1))
        if a1 is None:
            a1 = Annonce(
                owner_id=amira.id,
                titre=titre1,
                description="Studio meublé pour étudiant près de la faculté de Sousse, avec internet et eau chaude incluse dans le loyer.",
                type_bien=TypeBien.STUDIO,
                transaction=Transaction.LOCATION,
                prix=450,
                surface=30,
                nb_pieces=1,
                meuble=True,
                adresse="Rue des essais, Sousse",
                ville="Sousse",
                statut=StatutAnnonce.PUBLIEE,
            )
            session.add(a1)
            session.flush()

        # 2. Annonce maison de Mahdia avec photos 1 et 2 pour Amira
        titre2 = "Maison avec jardin et puits à Mahdia"
        a2 = session.scalar(select(Annonce).where(Annonce.owner_id == amira.id, Annonce.titre == titre2))
        if a2 is None:
            a2 = Annonce(
                owner_id=amira.id,
                titre=titre2,
                description="Maison avec jardin et puits à Mahdia",
                type_bien=TypeBien.MAISON,
                transaction=Transaction.LOCATION,
                prix=1400,
                surface=160,
                nb_pieces=5,
                meuble=False,
                adresse="Rue des essais, Mahdia",
                ville="Mahdia",
                statut=StatutAnnonce.PUBLIEE,
            )
            session.add(a2)
            session.flush()

            # Copie photo 1 et photo 2 dans le dossier uploads
            p1_dest = Path(dossier_uploads) / f"{uuid.uuid4().hex}.jpg"
            p2_dest = Path(dossier_uploads) / f"{uuid.uuid4().hex}.jpg"
            shutil.copyfile(photos["photo1"], p1_dest)
            shutil.copyfile(photos["photo2"], p2_dest)

            sha1, phash1 = empreintes_image(p1_dest.read_bytes())
            sha2, phash2 = empreintes_image(p2_dest.read_bytes())

            photo1_obj = AnnoncePhoto(annonce_id=a2.id, url=f"/uploads/{p1_dest.name}", ordre=1, sha256=sha1, phash=phash1)
            photo2_obj = AnnoncePhoto(annonce_id=a2.id, url=f"/uploads/{p2_dest.name}", ordre=2, sha256=sha2, phash=phash2)
            session.add_all([photo1_obj, photo2_obj])

        session.commit()

    click.echo(f"Base de démonstration prête : {base_path}")
    click.echo(f"Photos de démonstration générées dans : {dossier_photos}")


@click.command("entrainer-absence-visites")
@with_appcontext
def entrainer_absence_visites() -> None:
    """Réentraîne le modèle de risque d'absence depuis l'historique des visites."""
    from app.services.planification_absence import entrainer_et_sauver

    predicteur, nombre = entrainer_et_sauver()
    if predicteur.pret:
        click.echo(f"Modèle de risque d'absence entraîné avec {nombre} visites terminées.")
    else:
        click.echo(
            f"Historique insuffisant ou à une seule classe ({nombre} visites terminées); "
            "les règles fixes restent actives."
        )


@click.command("entrainer-classement-annonces")
@click.option("--graine", default=42, show_default=True, help="Graine du jeu simulé d'entraînement.")
@with_appcontext
def entrainer_classement_annonces(graine: int) -> None:
    """Entraîne le classement LambdaRank sur des données simulées (démonstration uniquement)."""
    from app.ia.classement_annonces import entrainer

    try:
        resultat = entrainer(Path(current_app.config["MODELES_FOLDER"]), graine=graine)
    except (RuntimeError, OSError, ValueError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(
        f"Classement LambdaRank entraîné sur {resultat['nb_recherches']} recherches simulées "
        f"et {resultat['nb_annonces']} annonces."
    )
    click.echo(f"Modèle local : {resultat['chemin']}")
    click.echo("Ces données simulées ne démontrent pas un gain sur de vrais visiteurs.")


@click.command("evaluer-classement-annonces")
@click.option("--graine", default=73, show_default=True, help="Graine de l'évaluation simulée.")
@with_appcontext
def evaluer_classement_annonces(graine: int) -> None:
    """Évalue LambdaRank contre l'ordre chronologique sur validation simulée."""
    from app.ia.classement_annonces import evaluer_simule

    try:
        resultat = evaluer_simule(graine=graine)
    except (RuntimeError, ValueError) as erreur:
        raise click.ClickException(str(erreur)) from erreur
    click.echo(json.dumps(resultat, ensure_ascii=True, indent=2))

