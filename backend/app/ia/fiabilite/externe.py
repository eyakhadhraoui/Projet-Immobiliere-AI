"""Évaluation en lecture seule sur les paires externes fournies avec le kit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ia.fiabilite.service import normaliser_texte
from app.ia.fiabilite.texte import encodeur_local


class JeuExterneInvalide(ValueError):
    """Le fichier externe ne respecte pas le format attendu."""


def charger_paires(chemin: str | Path) -> list[dict[str, Any]]:
    """Lit exactement 20 paires étiquetées sans doublon.

    ``B: [H] ...`` conserve le marqueur comme métadonnée et enlève son préfixe du texte.
    """
    blocs: list[list[str]] = []
    courant: list[str] = []
    for ligne in Path(chemin).read_text(encoding="utf-8-sig").splitlines():
        propre = ligne.strip()
        if not propre or propre.startswith("#"):
            if courant:
                blocs.append(courant)
                courant = []
            continue
        courant.append(propre)
    if courant:
        blocs.append(courant)

    resultat: list[dict[str, Any]] = []
    signatures: set[tuple[str, str, str]] = set()
    for numero, bloc in enumerate(blocs, start=1):
        if len(bloc) != 3 or bloc[0] not in {"DOUBLON", "DIFFERENT"}:
            raise JeuExterneInvalide(f"Bloc {numero}: format attendu DOUBLON/DIFFERENT, A: et B:.")
        if not bloc[1].startswith("A:") or not bloc[2].startswith("B:"):
            raise JeuExterneInvalide(f"Bloc {numero}: les lignes A: et B: sont requises.")
        texte_a = bloc[1][2:].strip()
        texte_b = bloc[2][2:].strip()
        humain = texte_b.startswith("[H]")
        if humain:
            texte_b = texte_b[3:].strip()
        if not texte_a or not texte_b:
            raise JeuExterneInvalide(f"Bloc {numero}: textes vides.")
        a_norm, b_norm = normaliser_texte(texte_a), normaliser_texte(texte_b)
        if not a_norm or not b_norm or a_norm == b_norm:
            raise JeuExterneInvalide(f"Bloc {numero}: les deux textes doivent être distincts et non vides.")
        signature = (bloc[0], *sorted((a_norm, b_norm)))
        if signature in signatures:
            raise JeuExterneInvalide(f"Bloc {numero}: paire dupliquée.")
        signatures.add(signature)
        resultat.append({"id": numero, "label": bloc[0], "doublon": bloc[0] == "DOUBLON",
                         "texte_a": texte_a, "texte_b": texte_b, "humain": humain})
    positifs = sum(p["doublon"] for p in resultat)
    negatifs = len(resultat) - positifs
    if len(resultat) != 20 or positifs != 10 or negatifs != 10:
        raise JeuExterneInvalide(f"Il faut 20 paires: 10 DOUBLON et 10 DIFFERENT; trouvé {len(resultat)} ({positifs}/{negatifs}).")
    return resultat


def _mesures(vrai: np.ndarray, predit: np.ndarray) -> dict[str, Any]:
    vp = int(np.sum(vrai & predit))
    fp = int(np.sum(~vrai & predit))
    fn = int(np.sum(vrai & ~predit))
    vn = int(np.sum(~vrai & ~predit))
    precision = vp / (vp + fp) if vp + fp else 0.0
    rappel = vp / (vp + fn) if vp + fn else 0.0
    return {"vp": vp, "fp": fp, "fn": fn, "vn": vn, "precision": precision,
            "rappel": rappel, "f1": 2 * precision * rappel / (precision + rappel)
            if precision + rappel else 0.0,
            "taux_faux_positifs": fp / (fp + vn) if fp + vn else 0.0}


def _intervalle_f1(vrai: np.ndarray, predit: np.ndarray) -> list[float]:
    rng = np.random.default_rng(2026)
    scores = []
    for _ in range(3000):
        indices = rng.integers(0, len(vrai), len(vrai))
        scores.append(float(_mesures(vrai[indices], predit[indices])["f1"]))
    return [float(np.quantile(scores, 0.025)), float(np.quantile(scores, 0.975))]


def evaluer_test_externe(chemin: str | Path, dossier_modeles: str | Path) -> dict[str, Any]:
    """Compare règles exactes, TF-IDF et LoRA si disponible, sans toucher aux seuils."""
    paires = charger_paires(chemin)
    dossier = Path(dossier_modeles)
    seuil_path = dossier / "fiabilite" / "seuils.json"
    config = json.loads(seuil_path.read_text(encoding="utf-8")) if seuil_path.is_file() else {}
    seuils = config.get("seuils", {})
    seuil_tfidf = float(seuils.get("texte_tfidf", seuils.get("tfidf", 0.75)))
    y = np.asarray([p["doublon"] for p in paires], dtype=bool)
    pred_exacte = np.asarray([
        normaliser_texte(p["texte_a"]) == normaliser_texte(p["texte_b"]) for p in paires
    ], dtype=bool)
    scores_tfidf = []
    for paire in paires:
        vecteurs = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(
            [normaliser_texte(paire["texte_a"]), normaliser_texte(paire["texte_b"])]
        )
        scores_tfidf.append(float(cosine_similarity(vecteurs[0:1], vecteurs[1:2])[0, 0]))
    pred_tfidf = np.asarray(scores_tfidf) >= seuil_tfidf

    encodeur = encodeur_local(str(dossier))
    utilise_lora = encodeur.disponible
    pred_lora: np.ndarray | None = None
    scores_lora: list[float] = []
    seuil_lora = float(seuils.get("embedding", 0.79))
    if utilise_lora:
        for paire in paires:
            vecteurs = encodeur.encoder([paire["texte_a"], paire["texte_b"]])
            scores_lora.append(float(vecteurs[0] @ vecteurs[1]))
        pred_lora = np.asarray(scores_lora) >= seuil_lora

    candidats: dict[str, np.ndarray] = {"texte_identique": pred_exacte, "tfidf": pred_tfidf}
    if pred_lora is not None:
        candidats["minilm_lora"] = pred_lora
    rapports = {}
    for nom, prediction in candidats.items():
        mesures = _mesures(y, prediction)
        mesures["ic95_f1"] = _intervalle_f1(y, prediction)
        humain = np.asarray([p["humain"] for p in paires], dtype=bool)
        mesures["paires_humaines"] = int(np.sum(humain))
        mesures["f1_paires_humaines"] = (
            float(_mesures(y[humain], prediction[humain])["f1"]) if np.any(humain) else None
        )
        mesures["f1_autres_paires"] = float(_mesures(y[~humain], prediction[~humain])["f1"])
        rapports[nom] = mesures

    ordre_simplicite = {"texte_identique": 0, "tfidf": 1, "minilm_lora": 2}
    classement = sorted(candidats, key=lambda nom: (
        -float(rapports[nom]["f1"]), int(rapports[nom]["fp"]), ordre_simplicite[nom]
    ))
    lignes = [{"id": paire["id"], "label": paire["label"], "humaine": paire["humain"],
               "exact": bool(pred_exacte[index]), "tfidf_score": scores_tfidf[index],
               "tfidf": bool(pred_tfidf[index]),
               "lora_score": scores_lora[index] if scores_lora else None,
               "lora": bool(pred_lora[index]) if pred_lora is not None else None}
              for index, paire in enumerate(paires)]
    return {
        "paires": len(paires), "doublons": int(y.sum()), "differentes": int((~y).sum()),
        "modele_production_configure": config.get("decision_production"),
        "modele_production_disponible": utilise_lora,
        "seuils_utilises_sans_modification": {"tfidf": seuil_tfidf, "minilm_lora": seuil_lora},
        "resultats": rapports, "classement_regle": classement,
        "recommandation": ("LoRA indisponible localement; aucune recommandation de remplacement."
                           if not utilise_lora else
                           f"Meilleur résultat externe selon la règle: {classement[0]}. Choix à confirmer; aucun seuil changé."),
        "paires_detaillees": lignes,
        "fichier_seuils_modifie": False,
    }
