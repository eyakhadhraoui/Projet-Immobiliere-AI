"""Génération d'annonces de démonstration pour entraîner l'estimation du prix (IA-ANNONCE-001).

POURQUOI : la base ne contient que quelques vraies annonces, trop peu pour entraîner un modèle. On génère donc
des annonces « réalistes » pour la Tunisie, clairement marquées « [DÉMO] » et rattachées à un compte dédié.

LIMITE IMPORTANTE (à dire à l'oral) : les prix sont calculés par les règles ci-dessous. Un modèle entraîné sur ces
données apprend CES règles, pas le vrai marché tunisien. Les prix au m² sont des ordres de grandeur choisis pour la
démonstration, pas le résultat d'une étude de marché.

Règle de calcul du prix (tout est multiplicatif) :

    prix = surface × prix_m2_ville(transaction)
           × coefficient_type × coefficient_etat × coefficient_meuble(transaction)
           × produit des coefficients d'équipements
           × bruit aléatoire (loi log-normale, écart-type 0,12 ≈ ±12 %)

L'« état » du bien (neuf, bon état, à rafraîchir) influence le prix mais n'est PAS une variable du modèle (il n'est
écrit que dans la description) : c'est volontairement une part du prix que le modèle ne peut pas expliquer, comme
dans la réalité.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

# --- Règles de génération -------------------------------------------------------------------------------------

# Ville → (latitude, longitude, prix de vente au m² en TND, loyer mensuel au m² en TND).
# Ordres de grandeur approximatifs, choisis pour la démonstration (non issus d'une étude de marché).
VILLES: dict[str, tuple[float, float, float, float]] = {
    "La Marsa": (36.8782, 10.3247, 4000, 14.0),
    "Tunis": (36.8065, 10.1815, 2600, 10.0),
    "Ariana": (36.8665, 10.1647, 2300, 9.0),
    "Hammamet": (36.4000, 10.6167, 2300, 9.5),
    "Sousse": (35.8256, 10.6360, 2000, 8.0),
    "Ben Arous": (36.7531, 10.2189, 1900, 7.5),
    "Monastir": (35.7643, 10.8113, 1800, 7.5),
    "Nabeul": (36.4561, 10.7376, 1600, 6.5),
    "Bizerte": (37.2744, 9.8739, 1550, 6.0),
    "Sfax": (34.7406, 10.7603, 1600, 6.5),
}
# Les grandes villes reçoivent plus d'annonces (poids de tirage).
POIDS_VILLES = {"La Marsa": 9, "Tunis": 16, "Ariana": 11, "Hammamet": 8, "Sousse": 12, "Ben Arous": 8,
                "Monastir": 7, "Nabeul": 8, "Bizerte": 6, "Sfax": 10}

# Type de bien → (coefficient de prix au m², surface min, surface max, poids de tirage).
TYPES: dict[str, tuple[float, int, int, int]] = {
    "appartement": (1.00, 55, 160, 45),
    "studio": (1.12, 25, 45, 12),
    "maison": (0.95, 90, 250, 20),
    "villa": (1.25, 180, 450, 13),
    "residence": (1.05, 60, 140, 10),
}

# État du bien → (coefficient, phrase de description, poids). Non utilisé comme variable par le modèle.
ETATS: dict[str, tuple[float, str, int]] = {
    "neuf": (1.12, "Bien neuf, jamais habité, finitions de qualité.", 20),
    "bon": (1.00, "Bien en bon état général.", 60),
    "a_rafraichir": (0.85, "Quelques travaux de rafraîchissement à prévoir.", 20),
}

# Équipement → (coefficient de prix, probabilité de présence). La piscine et le jardin sont plus fréquents
# pour les villas et maisons (voir _tirer_equipements).
EQUIPEMENTS: dict[str, tuple[float, float]] = {
    "parking": (1.05, 0.45),
    "climatisation": (1.03, 0.60),
    "ascenseur": (1.03, 0.35),
    "balcon": (1.02, 0.50),
    "jardin": (1.06, 0.20),
    "piscine": (1.12, 0.08),
    "chauffage": (1.02, 0.40),
    "internet": (1.01, 0.55),
}

COEF_MEUBLE = {"location": 1.15, "vente": 1.03}  # un bien meublé se loue nettement plus cher
ECART_TYPE_BRUIT = 0.12  # bruit log-normal : ±12 % environ autour de la règle
PROPORTION_LOCATION = 0.55
GRAINE_PAR_DEFAUT = 2026
PREFIXE_TITRE = "[DÉMO]"

EMAIL_PROPRIETAIRE_DEMO = "proprietaire.annonces-demo@example.com"
# Seul le prénom est publié sur la fiche (« Proposé par Agence Démo ») : il doit donc se lire comme un nom
# d'annonceur réaliste, tout en restant clairement une démonstration.
PRENOM_PROPRIETAIRE_DEMO = "Agence Démo"
NOM_PROPRIETAIRE_DEMO = "Immobilier"

QUARTIERS = {
    "La Marsa": ["Marsa Plage", "Sidi Abdelaziz", "Marsa Ville"], "Tunis": ["Lafayette", "El Menzah", "Centre-ville"],
    "Ariana": ["Ennasr", "Riadh Andalous", "Ariana Ville"], "Hammamet": ["Hammamet Nord", "Yasmine Hammamet"],
    "Sousse": ["Khezama", "Sahloul", "Sousse Corniche"], "Ben Arous": ["Mégrine", "Ezzahra", "Radès"],
    "Monastir": ["Skanes", "Monastir Centre"], "Nabeul": ["Nabeul Plage", "Beni Khiar"],
    "Bizerte": ["Corniche de Bizerte", "Zarzouna"], "Sfax": ["Sfax El Jadida", "Route de Tunis", "Sakiet Ezzit"],
}
ATOUTS = [
    "Proche des écoles et des commerces.", "À quelques minutes des transports.", "Quartier calme et résidentiel.",
    "Belle luminosité toute la journée.", "Vue dégagée.", "Cuisine ouverte sur le séjour.",
    "Rangements nombreux.", "Idéal pour une famille.", "Proche de la plage.", "Double vitrage.",
]
NOMS_EQUIPEMENTS = {"parking": "place de parking", "climatisation": "climatisation", "ascenseur": "ascenseur",
                    "balcon": "balcon", "jardin": "jardin", "piscine": "piscine", "chauffage": "chauffage central",
                    "internet": "connexion internet"}
LIBELLES_TYPES = {"appartement": "Appartement", "studio": "Studio", "maison": "Maison", "villa": "Villa",
                  "residence": "Résidence"}


@dataclass(frozen=True)
class AnnonceDemo:
    """Données d'une annonce générée (champs du modèle Annonce, sans owner_id)."""

    titre: str
    description: str
    type_bien: str
    transaction: str
    prix: float
    surface: float
    nb_pieces: int
    meuble: bool
    adresse: str
    ville: str
    latitude: float
    longitude: float
    caracteristiques: list[str]
    statut: str


def _tirer_equipements(alea: random.Random, type_bien: str) -> list[str]:
    """Tire les équipements présents (piscine et jardin plus fréquents pour une villa ou une maison).

    Args:
        alea: Générateur aléatoire (graine fixe).
        type_bien: Type de bien.

    Returns:
        list[str]: Équipements, triés.
    """
    equipements = []
    for nom, (_coef, probabilite) in EQUIPEMENTS.items():
        if nom in ("piscine", "jardin") and type_bien in ("villa", "maison"):
            probabilite *= 4
        if nom == "ascenseur" and type_bien in ("villa", "maison"):
            probabilite = 0.0  # pas d'ascenseur dans une maison individuelle
        if alea.random() < min(probabilite, 0.9):
            equipements.append(nom)
    return sorted(equipements)


def prix_selon_regles(
    ville: str, type_bien: str, transaction: str, surface: float, meuble: bool, equipements: list[str], etat: str
) -> float:
    """Prix « théorique » d'un bien selon les règles de génération, sans bruit.

    Args:
        ville: Ville (clé de VILLES).
        type_bien: Type de bien (clé de TYPES).
        transaction: ``"vente"`` ou ``"location"``.
        surface: Surface en m².
        meuble: Bien meublé.
        equipements: Équipements présents.
        etat: État du bien (clé de ETATS).

    Returns:
        float: Prix en TND (prix de vente, ou loyer mensuel).
    """
    _lat, _lon, prix_m2_vente, loyer_m2 = VILLES[ville]
    prix = surface * (loyer_m2 if transaction == "location" else prix_m2_vente)
    prix *= TYPES[type_bien][0] * ETATS[etat][0]
    if meuble:
        prix *= COEF_MEUBLE[transaction]
    for nom in equipements:
        prix *= EQUIPEMENTS[nom][0]
    return prix


def _arrondir(prix: float, transaction: str) -> float:
    """Arrondit comme un vrai annonceur : à 10 TND pour un loyer, à 1 000 TND pour une vente."""
    pas = 10 if transaction == "location" else 1000
    return max(pas, round(prix / pas) * pas)


def generer_annonces(nombre: int, graine: int = GRAINE_PAR_DEFAUT) -> list[AnnonceDemo]:
    """Génère des annonces de démonstration reproductibles (même graine → mêmes annonces).

    Args:
        nombre: Nombre d'annonces.
        graine: Graine du générateur aléatoire.

    Returns:
        list[AnnonceDemo]: Annonces générées.
    """
    alea = random.Random(graine)
    villes, poids_villes = list(POIDS_VILLES), list(POIDS_VILLES.values())
    types, poids_types = list(TYPES), [t[3] for t in TYPES.values()]
    etats, poids_etats = list(ETATS), [e[2] for e in ETATS.values()]
    annonces = []
    for _ in range(nombre):
        ville = alea.choices(villes, poids_villes)[0]
        type_bien = alea.choices(types, poids_types)[0]
        # Les villas se vendent plus souvent qu'elles ne se louent, les studios l'inverse.
        part_location = {"villa": 0.35, "studio": 0.80}.get(type_bien, PROPORTION_LOCATION)
        transaction = "location" if alea.random() < part_location else "vente"
        _coef, surface_min, surface_max, _poids = TYPES[type_bien]
        surface = float(alea.randint(surface_min, surface_max))
        nb_pieces = 1 if type_bien == "studio" else max(2, min(9, round(surface / 32) + alea.randint(-1, 1)))
        meuble = alea.random() < (0.45 if transaction == "location" else 0.10)
        equipements = _tirer_equipements(alea, type_bien)
        etat = alea.choices(etats, poids_etats)[0]

        prix = prix_selon_regles(ville, type_bien, transaction, surface, meuble, equipements, etat)
        prix *= math.exp(alea.gauss(0, ECART_TYPE_BRUIT))  # bruit : deux biens identiques n'ont pas le même prix
        prix = _arrondir(prix, transaction)

        lat, lon, _pv, _pl = VILLES[ville]
        quartier = alea.choice(QUARTIERS[ville])
        libelle = "Studio" if type_bien == "studio" else f"{LIBELLES_TYPES[type_bien]} S+{nb_pieces - 1}"
        equip_texte = ", ".join(NOMS_EQUIPEMENTS[e] for e in equipements) or "aucun équipement particulier"
        description = " ".join([
            f"{LIBELLES_TYPES[type_bien]} de {int(surface)} m² à {quartier}, {ville}.",
            ETATS[etat][1],
            *alea.sample(ATOUTS, 2),
            f"Équipements : {equip_texte}.",
            "Meublé." if meuble else "Non meublé.",
            "Annonce générée automatiquement pour la démonstration.",
        ])
        # La plupart sont publiées ; quelques brouillons, et quelques biens déjà loués ou vendus.
        tirage = alea.random()
        if tirage < 0.85:
            statut = "publiee"
        elif tirage < 0.93:
            statut = "brouillon"
        else:
            statut = "louee" if transaction == "location" else "vendue"

        annonces.append(AnnonceDemo(
            titre=f"{PREFIXE_TITRE} {libelle} à {quartier}",
            description=description,
            type_bien=type_bien,
            transaction=transaction,
            prix=prix,
            surface=surface,
            nb_pieces=nb_pieces,
            meuble=meuble,
            adresse=f"{alea.randint(1, 120)} rue {alea.choice(['des Jasmins', 'Ibn Khaldoun', 'de la Liberté', 'Habib Thameur', 'des Oliviers'])}, {quartier}",
            ville=ville,
            latitude=round(lat + alea.uniform(-0.02, 0.02), 5),
            longitude=round(lon + alea.uniform(-0.02, 0.02), 5),
            caracteristiques=equipements,
            statut=statut,
        ))
    return annonces


def en_dict(annonce: AnnonceDemo) -> dict[str, Any]:
    """Champs à passer au constructeur ``Annonce``.

    Args:
        annonce: Annonce générée.

    Returns:
        dict[str, Any]: Champs du modèle.
    """
    return dict(annonce.__dict__)
