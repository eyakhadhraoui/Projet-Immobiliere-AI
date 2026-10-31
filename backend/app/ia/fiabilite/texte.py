"""Embeddings MiniLM + LoRA chargés hors ligne, avec repli TF-IDF."""

from __future__ import annotations

import os
import json
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


NOM_BASE = "paraphrase-multilingual-MiniLM-L12-v2"
REVISION_BASE = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


class ModeleTexteIndisponible(RuntimeError):
    """Le modèle local MiniLM ou son adaptateur ne peut pas être chargé."""


class EncodeurLoRA:
    """Encodeur local thread-safe chargé à la demande et limité au CPU."""

    def __init__(self, dossier_modeles: str | Path):
        self.dossier = Path(dossier_modeles)
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()

    @property
    def disponible(self) -> bool:
        try:
            self._charger()
            return True
        except Exception:  # noqa: BLE001 — le module doit toujours pouvoir utiliser son repli local
            return False

    def _charger(self) -> None:
        if self._model is not None:
            return
        base = self.dossier / "texte" / NOM_BASE
        adaptateur = self.dossier / "fiabilite" / "lora"
        if not base.is_dir() or not adaptateur.is_dir():
            raise ModeleTexteIndisponible("Modèle MiniLM ou adaptateur LoRA absent.")
        manifest_path = base / "fiabilite_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erreur:
            raise ModeleTexteIndisponible("Manifest du modèle local absent ou invalide.") from erreur
        if manifest.get("revision") != REVISION_BASE:
            raise ModeleTexteIndisponible("La révision du modèle local ne correspond pas à celle de l'adaptateur.")
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModel, AutoTokenizer
        except ImportError as erreur:
            raise ModeleTexteIndisponible("Dépendances locales LoRA absentes.") from erreur
        tokenizer = AutoTokenizer.from_pretrained(str(base), local_files_only=True)
        modele = AutoModel.from_pretrained(str(base), local_files_only=True)
        modele = PeftModel.from_pretrained(modele, str(adaptateur), local_files_only=True)
        modele.eval()
        modele.to("cpu")
        self._torch, self._tokenizer, self._model = torch, tokenizer, modele

    def encoder(self, textes: list[str]) -> np.ndarray:
        """Encode les textes en lots de taille 32 et renvoie des vecteurs normalisés."""
        self._charger()
        if not textes:
            return np.empty((0, 384), dtype=np.float32)
        for debut in range(0, len(textes), 32):
            lot = textes[debut:debut + 32]
            nouveaux = list(dict.fromkeys(texte for texte in lot if texte not in self._cache))
            if not nouveaux:
                continue
            tokens = self._tokenizer(nouveaux, return_tensors="pt", padding=True,
                                     truncation=True, max_length=128)
            with self._torch.inference_mode():
                sortie = self._model(**tokens).last_hidden_state
                masque = tokens["attention_mask"].unsqueeze(-1).expand(sortie.size()).float()
                vecteurs = (sortie * masque).sum(1) / masque.sum(1).clamp(min=1e-9)
                vecteurs = self._torch.nn.functional.normalize(vecteurs, p=2, dim=1).cpu().numpy()
            for texte, vecteur in zip(nouveaux, vecteurs):
                self._cache[texte] = tuple(float(x) for x in vecteur)
                self._cache.move_to_end(texte)
                if len(self._cache) > 5000:
                    self._cache.popitem(last=False)
        return np.asarray([self._cache[texte] for texte in textes], dtype=np.float32)


def telecharger_modele_base(dossier_modeles: str | Path) -> Path:
    """Télécharge une seule révision épinglée du modèle public Hugging Face.

    Cette fonction est réservée à la commande explicite d'installation. Le service de
    publication ne télécharge jamais de modèle et reste hors ligne.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as erreur:
        raise ModeleTexteIndisponible("huggingface_hub n'est pas installé.") from erreur
    cible = Path(dossier_modeles) / "texte" / NOM_BASE
    cible.mkdir(parents=True, exist_ok=True)
    mode_hors_ligne = os.environ.pop("HF_HUB_OFFLINE", None)
    try:
        snapshot_download(repo_id=f"sentence-transformers/{NOM_BASE}", revision=REVISION_BASE,
                          local_dir=str(cible), allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "*.bin"])
    finally:
        if mode_hors_ligne is not None:
            os.environ["HF_HUB_OFFLINE"] = mode_hors_ligne
    (cible / "fiabilite_manifest.json").write_text(
        json.dumps({"repo_id": f"sentence-transformers/{NOM_BASE}", "revision": REVISION_BASE}, indent=2),
        encoding="utf-8",
    )
    return cible


@lru_cache(maxsize=2)
def encodeur_local(dossier_modeles: str) -> EncodeurLoRA:
    """Réutilise un encodeur par dossier de modèle pendant la vie du processus."""
    return EncodeurLoRA(dossier_modeles)
