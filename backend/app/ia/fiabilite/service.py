"""Comparaison d'annonces à la publication, avec repli TF-IDF local."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import select
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app import db
from app.ia import anomalies_annonces, estimation_prix
from app.ia.fiabilite import VERSION
from app.ia.fiabilite.empreintes import distance_hamming
from app.ia.fiabilite.texte import encodeur_local
from app.models import Annonce, AnnoncePhoto, StatutAnnonce


SEUILS_PAR_DEFAUT = {
    "tfidf": 0.75,
    "hamming": 6,
    "embedding": 0.79,
    "regle_photos": "nombre_de_photos",
    "modele_texte": "tfidf",
    "anomalies_ecart_prix": 0.95,
}
STATUTS_PUBLICS = (StatutAnnonce.PUBLIEE, StatutAnnonce.LOUEE, StatutAnnonce.VENDUE)


def normaliser_texte(texte: str) -> str:
    """Normalise la casse, les accents, la ponctuation et les espaces."""
    texte = unicodedata.normalize("NFKD", texte.casefold())
    texte = "".join(car for car in texte if not unicodedata.combining(car))
    return " ".join("".join(car if car.isalnum() else " " for car in texte).split())


def _seuils(dossier: Path) -> dict[str, Any]:
    import json

    chemin = dossier / "fiabilite" / "seuils.json"
    if not chemin.is_file():
        return SEUILS_PAR_DEFAUT.copy()
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        return {**SEUILS_PAR_DEFAUT, **contenu.get("seuils", {})}
    except (OSError, ValueError, TypeError):
        return SEUILS_PAR_DEFAUT.copy()


def _photos_proches(photos_a: list[AnnoncePhoto], photos_b: list[AnnoncePhoto], seuil: int) -> list[dict[str, Any]]:
    """Apparie une seule fois les photos identiques ou proches, du meilleur au moins bon."""
    candidats: list[tuple[int, int, int, bool]] = []
    for a in photos_a[:10]:
        for b in photos_b[:10]:
            identical = bool(a.sha256 and b.sha256 and a.sha256 == b.sha256)
            if identical:
                distance = 0
            elif a.phash and b.phash:
                distance = distance_hamming(a.phash, b.phash)
            else:
                continue
            if identical or distance <= seuil:
                candidats.append((distance, a.id, b.id, identical))
    candidats.sort(key=lambda item: (not item[3], item[0]))
    util_a: set[int] = set()
    util_b: set[int] = set()
    resultat = []
    for distance, id_a, id_b, identical in candidats:
        if id_a in util_a or id_b in util_b:
            continue
        util_a.add(id_a)
        util_b.add(id_b)
        resultat.append({"photo_id_a": id_a, "photo_id_b": id_b,
                         "distance": distance, "identique": identical})
    return resultat


def _caracteristiques_proches(a: Annonce, b: Annonce) -> bool:
    """Indique si les caractéristiques structurelles sont très proches."""
    ville_a, ville_b = normaliser_texte(a.ville), normaliser_texte(b.ville)
    if (a.transaction != b.transaction or a.type_bien != b.type_bien or ville_a != ville_b
            or a.nb_pieces != b.nb_pieces):
        return False
    surface_ok = abs(a.surface - b.surface) / max(a.surface, b.surface) <= 0.05
    prix_ok = abs(a.prix - b.prix) / max(a.prix, b.prix) <= 0.10
    return surface_ok and prix_ok


def _estimation_ecart(annonce: Annonce, dossier: Path) -> tuple[bool, float | None]:
    """Compare le prix à l'estimation locale si le modèle de marché est disponible."""
    donnees = {
        "type_bien": annonce.type_bien.value,
        "transaction": annonce.transaction.value,
        "prix": float(annonce.prix),
        "surface": float(annonce.surface),
        "nb_pieces": int(annonce.nb_pieces),
        "ville": annonce.ville,
        "meuble": bool(annonce.meuble),
        "caracteristiques": annonce.caracteristiques or [],
    }
    try:
        estime = estimation_prix.estimer(donnees, dossier)
        prix_estime = float(estime["prix_estime"])
        ecart_log = abs(__import__("math").log(max(float(annonce.prix), 1) / max(prix_estime, 1)))
        return ecart_log >= 0.95, ecart_log
    except (KeyError, TypeError, ValueError, OSError, estimation_prix.ModeleIndisponible):
        return False, None


def _anomalies(annonce: Annonce, dossier: Path) -> tuple[int, list[dict[str, str]]]:
    prix_m2 = float(annonce.prix) / float(annonce.surface)
    borne_hors = ((annonce.transaction == "location" and not 1 <= prix_m2 <= 100)
                  or (annonce.transaction == "vente" and not 200 <= prix_m2 <= 20_000))
    points = 40 if borne_hors else 0
    raisons: list[dict[str, str]] = []
    if borne_hors:
        raisons.append({"type": "prix", "signal": "prix_m2_hors_bornes",
                        "texte": "Le prix au m² s’écarte fortement des plages de référence du projet."})
    donnees = {"prix": float(annonce.prix), "surface": float(annonce.surface),
               "nb_pieces": int(annonce.nb_pieces), "transaction": annonce.transaction.value,
               "type_bien": annonce.type_bien.value, "ville": annonce.ville}
    try:
        anomalie = anomalies_annonces.analyser(donnees, dossier)
        if anomalie.get("disponible") and anomalie.get("niveau") == "à_verifier":
            points += 25
            raisons.append({"type": "anomalie", "signal": "profil_statistique_atypique",
                            "texte": "La combinaison prix, surface et nombre de pièces est inhabituelle."})
    except (FileNotFoundError, ValueError, KeyError, OSError):
        pass
    ecart, _ = _estimation_ecart(annonce, dossier)
    if ecart:
        points += 25
        raisons.append({"type": "prix", "signal": "ecart_estimation",
                        "texte": "Le prix s’écarte nettement de l’estimation indicative du marché."})
    return min(points, 100), raisons


def analyser_annonce(annonce: Annonce, dossier_modeles: str | Path) -> dict[str, Any]:
    """Retourne score, niveau et signaux privés pour le dernier contrôle.

    La recherche compare les annonces déjà publiques ou ayant été publiées, y compris
    les autres annonces du même propriétaire. Le détail privé reste dans ``doublons``.
    """
    dossier = Path(dossier_modeles)
    seuils = _seuils(dossier)
    candidates = db.session.scalars(
        select(Annonce).where(Annonce.id != annonce.id,
                              Annonce.statut.in_(STATUTS_PUBLICS))
        .order_by(Annonce.updated_at.desc()).limit(2000)
    ).unique().all()
    texte = normaliser_texte(annonce.description)
    textes = [normaliser_texte(c.description) for c in candidates]
    similarites: list[float] = []
    seuil_texte = float(seuils["tfidf"])
    modele_texte = "tfidf"
    if texte and textes:
        encodeur = encodeur_local(str(dossier))
        try:
            if not encodeur.disponible:
                raise RuntimeError("Encodeur local indisponible")
            vecteurs = encodeur.encoder([annonce.description, *(c.description for c in candidates)])
            similarites = (vecteurs[1:] @ vecteurs[0]).astype(float).tolist()
            seuil_texte = float(seuils["embedding"])
            modele_texte = "minilm_lora"
        except Exception:  # noqa: BLE001 — le contrôle reste disponible avec TF-IDF
            try:
                matrice = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(
                    [texte, *textes]
                )
                similarites = cosine_similarity(matrice[0:1], matrice[1:]).ravel().tolist()
            except ValueError:
                similarites = [0.0] * len(candidates)

    doublons = []
    for index, candidate in enumerate(candidates):
        autre_proprietaire = candidate.owner_id != annonce.owner_id
        similarity = similarites[index] if similarites else 0.0
        text_identique = bool(autre_proprietaire and texte and texte == textes[index])
        text_proche = (autre_proprietaire and not text_identique and similarity >= seuil_texte)
        photos = _photos_proches(annonce.photos, candidate.photos, int(seuils["hamming"]))
        fields_close = autre_proprietaire and _caracteristiques_proches(annonce, candidate)
        points = 0
        signaux: list[str] = []
        raisons: list[dict[str, str]] = []
        if text_identique:
            points += 40
            signaux.append("description_identique")
            raisons.append({"type": "texte", "signal": "description_identique",
                            "texte": "La description ressemble fortement à celle d’une autre annonce."})
        elif text_proche:
            points += 30
            signaux.append("description_proche")
            raisons.append({"type": "texte", "signal": "description_proche",
                            "texte": "La description ressemble à des descriptions déjà présentes sur le site."})
        if photos:
            points += 50 if len(photos) >= 2 or photos[0]["identique"] else 40
            signaux.append("photos_proches")
            raisons.append({"type": "photo", "signal": "photos_communes",
                            "texte": "Une ou plusieurs photos ressemblent à celles d’une autre annonce."})
        if fields_close:
            points += 15
            signaux.append("caracteristiques_proches")
            raisons.append({"type": "caracteristiques", "signal": "caracteristiques_proches",
                            "texte": "Plusieurs caractéristiques de l’annonce sont très proches d’une autre annonce."})
        if points:
            doublons.append({"annonce_id": candidate.id, "points": min(points, 100),
                             "signaux": signaux, "raisons": raisons, "paires_photos": photos})
    doublons.sort(key=lambda item: item["points"], reverse=True)
    score_doublon = doublons[0]["points"] if doublons else 0
    empreintes_refusees = annonce.empreintes_refusees or []
    photos_refusees = []
    for photo in annonce.photos:
        for empreinte in empreintes_refusees:
            sha_identique = bool(photo.sha256 and empreinte.get("sha256")
                                 and photo.sha256 == empreinte.get("sha256"))
            phash_proche = bool(photo.phash and empreinte.get("phash")
                                and distance_hamming(photo.phash, empreinte["phash"])
                                <= int(seuils["hamming"]))
            if sha_identique or phash_proche:
                photos_refusees.append(photo.id)
                break
    raisons_photos_refusees = []
    if photos_refusees:
        score_doublon = max(score_doublon, 60)
        raisons_photos_refusees.append({
            "type": "photo",
            "signal": "photo_deja_refusee",
            "texte": "Votre annonce est en attente de vérification : une photo déjà refusée est toujours présente. "
                     "Remplacez-la par votre propre photo. Si vous pensez qu'il s'agit d'une erreur, faites une réclamation.",
        })
    score_anomalie, raisons_anomalies = _anomalies(annonce, dossier)
    score = min(100, score_doublon + score_anomalie)
    raisons = (doublons[0]["raisons"] if doublons else []) + raisons_photos_refusees + raisons_anomalies
    if score == 0:
        niveau, decision = "aucun_signal", "publication_normale"
    elif score < 40:
        niveau, decision = "a_surveiller", "confirmation_requise"
    else:
        niveau, decision = "a_verifier", "mise_en_attente"
    return {"niveau": niveau, "score": score, "raisons": raisons, "doublons": doublons,
            "decision": decision, "modele_texte": modele_texte, "version": VERSION}


def identifiants_photos_en_cause(
    annonce: Annonce, controle: Any, dossier_modeles: str | Path
) -> list[int]:
    """Liste les photos actuelles encore liées au contrôle ou à un refus antérieur."""
    ids = {
        int(paire["photo_id_a"])
        for doublon in (controle.doublons or [])
        for paire in doublon.get("paires_photos", [])
        if paire.get("photo_id_a") is not None
    } if controle else set()
    signal_refus = any(
        raison.get("signal") == "photo_deja_refusee" for raison in (controle.raisons or [])
    ) if controle else False
    if signal_refus:
        seuil = int(_seuils(Path(dossier_modeles))["hamming"])
        for photo in annonce.photos:
            for empreinte in annonce.empreintes_refusees or []:
                sha_identique = bool(photo.sha256 and empreinte.get("sha256")
                                     and photo.sha256 == empreinte["sha256"])
                phash_proche = bool(photo.phash and empreinte.get("phash")
                                    and distance_hamming(photo.phash, empreinte["phash"]) <= seuil)
                if sha_identique or phash_proche:
                    ids.add(photo.id)
                    break
    actuelles = {photo.id for photo in annonce.photos}
    return sorted(ids & actuelles)


def liste_publique_doublons(controle: Any) -> list[dict[str, Any]]:
    """Sérialise les correspondances sans divulguer les annonces non publiques."""
    resultats = []
    for doublon in controle.doublons or []:
        autre = db.session.get(Annonce, doublon.get("annonce_id"))
        visible = bool(autre and autre.statut == StatutAnnonce.PUBLIEE)
        item: dict[str, Any] = {"points": doublon.get("points"), "signaux": doublon.get("signaux", [])}
        if visible:
            item.update({"annonce_id": autre.id, "titre": autre.titre, "url": f"/annonces/{autre.id}"})
            paires = {photo.id: photo for photo in autre.photos}
            # L'API ne renvoie des paires photos que si l'annonce liée est publique.
            item["paires_photos"] = [
                {"distance": pair["distance"], "identique": pair["identique"],
                 "url_votre_photo": _url_photo(pair.get("photo_id_a")),
                 "url_annonce_publique": _url_photo(pair.get("photo_id_b"), paires)}
                for pair in doublon.get("paires_photos", [])
            ]
        else:
            item["annonce"] = "une autre annonce"
        resultats.append(item)
    return resultats


def _url_photo(photo_id: int | None, photos: dict[int, AnnoncePhoto] | None = None) -> str | None:
    """Renvoie un chemin upload à partir d'une photo autorisée."""
    if photo_id is None:
        return None
    photo = (photos or {}).get(photo_id) or db.session.get(AnnoncePhoto, photo_id)
    return photo.url if photo else None
