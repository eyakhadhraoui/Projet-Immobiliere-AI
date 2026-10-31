"""Évaluation reproductible sur les annonces fictives du kit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ia.fiabilite.empreintes import distance_hamming
from app.ia.fiabilite.jeu import charger_jeu
from app.ia.fiabilite.service import normaliser_texte
from app.ia.fiabilite.texte import encodeur_local


def _mesures(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    tp = sum(v and p for v, p in zip(y_true, y_pred))
    fp = sum((not v) and p for v, p in zip(y_true, y_pred))
    fn = sum(v and (not p) for v, p in zip(y_true, y_pred))
    tn = sum((not v) and (not p) for v, p in zip(y_true, y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    rappel = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    return {"paires": len(y_true), "vp": tp, "fp": fp, "fn": fn, "vn": tn,
            "precision": precision, "rappel": rappel, "f1": f1,
            "taux_faux_positifs": fp / (fp + tn) if fp + tn else 0.0}


def evaluer_jeu(chemin_jeu: str | Path, dossier_modeles: str | Path) -> dict[str, Any]:
    """Mesure les paires positives/négatives sans modifier les seuils du modèle.

    Le vocabulaire TF-IDF est appris exclusivement sur l'entraînement. Le test sert
    uniquement à produire les métriques finales et n'est jamais utilisé pour régler un seuil.
    """
    jeu = charger_jeu(chemin_jeu)
    annonces = jeu["annonces"]
    seuil_path = Path(dossier_modeles) / "fiabilite" / "seuils.json"
    seuils = json.loads(seuil_path.read_text(encoding="utf-8"))["seuils"] if seuil_path.exists() else {}
    encodeur = encodeur_local(str(dossier_modeles))
    utilise_lora = encodeur.disponible
    mode = "minilm_lora" if utilise_lora else "tfidf_repli_local"
    seuil = float(seuils.get("embedding" if utilise_lora else "tfidf", 0.75))
    train = [a for a in annonces if a["ensemble"] == "entrainement"]
    train_textes = [normaliser_texte(a["description"]) for a in train]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    vectorizer.fit(train_textes)
    rapports: dict[str, Any] = {}
    for ensemble in ("validation", "test"):
        lignes = [a for a in annonces if a["ensemble"] == ensemble]
        if utilise_lora:
            vecteurs = encodeur.encoder([a["description"] for a in lignes])
            similarites = vecteurs @ vecteurs.T
        else:
            vecteurs = vectorizer.transform([normaliser_texte(a["description"]) for a in lignes])
            similarites = cosine_similarity(vecteurs)
        vrai: list[bool] = []
        predit: list[bool] = []
        exact_texte: list[bool] = []
        for i in range(len(lignes)):
            for j in range(i + 1, len(lignes)):
                a, b = lignes[i], lignes[j]
                # Les démos ont des identifiants de source uniques et servent de négatifs.
                doublon = a.get("origine") == "redigee" and a.get("source") == b.get("source")
                same_text = normaliser_texte(a["description"]) == normaliser_texte(b["description"])
                same_photo = bool(a.get("sha256") and a.get("sha256") == b.get("sha256"))
                near_photo = False
                if not same_photo and a.get("phash") and b.get("phash"):
                    near_photo = distance_hamming(a["phash"], b["phash"]) <= int(seuils.get("hamming", 6))
                score_text = float(similarites[i, j])
                vrai.append(bool(doublon))
                predit.append(bool(same_text or score_text >= seuil or same_photo or near_photo))
                exact_texte.append(bool(same_text))
        rapports[ensemble] = {
            "modele_texte": mode,
            "seuil_texte_non_modifie": seuil,
            "comparaison_texte_et_photos": _mesures(vrai, predit),
            "regle_texte_identique": _mesures(vrai, exact_texte),
            "labels_anomalie_prix_surface": None,
        }
    rapports["jeu"] = {"annonces": len(annonces), "train": len(train),
                       "validation": sum(a["ensemble"] == "validation" for a in annonces),
                       "test": sum(a["ensemble"] == "test" for a in annonces),
                       "groupes_sans_fuite": True,
                       "nature": "fictif; métriques de doublons; aucune étiquette d'anomalie prix/surface"}
    sortie = Path(dossier_modeles) / "fiabilite" / "rapport_evaluation.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(rapports, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapports
