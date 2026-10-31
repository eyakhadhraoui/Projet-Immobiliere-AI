/** Caractéristiques proposées en cases à cocher (valeur envoyée à l'API → libellé affiché). */
export const CARACTERISTIQUES = {
  parking: 'Parking',
  climatisation: 'Climatisation',
  ascenseur: 'Ascenseur',
  balcon: 'Balcon',
  jardin: 'Jardin',
  piscine: 'Piscine',
  chauffage: 'Chauffage',
  internet: 'Internet',
}

/** Valeurs d'un formulaire vide (les champs texte et nombre sont des chaînes, comme dans les <input>). */
export const VALEURS_VIDES = {
  titre: '',
  description: '',
  type_bien: '',
  transaction: '',
  prix: '',
  surface: '',
  nb_pieces: '',
  meuble: false,
  adresse: '',
  ville: '',
  latitude: '',
  longitude: '',
  caracteristiques: [],
  disponibilites: [],
}

/** Champs affichés par le formulaire (les erreurs de l'API sur d'autres champs sont affichées en tête). */
export const CHAMPS_FORMULAIRE = Object.keys(VALEURS_VIDES)

// Mêmes messages que le backend (backend/app/schemas/annonce_schema.py).
const OBLIGATOIRE = 'Champ obligatoire.'
const INVALIDE = 'Valeur invalide.'

const enChaine = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur))

/**
 * Convertit une annonce renvoyée par l'API en valeurs de formulaire.
 *
 * @param {object} annonce Annonce de l'API.
 * @returns {typeof VALEURS_VIDES} Valeurs pour AnnonceForm.
 */
export function versFormulaire(annonce) {
  return {
    titre: annonce.titre ?? '',
    description: annonce.description ?? '',
    type_bien: annonce.type_bien ?? '',
    transaction: annonce.transaction ?? '',
    prix: enChaine(annonce.prix),
    surface: enChaine(annonce.surface),
    nb_pieces: enChaine(annonce.nb_pieces),
    meuble: Boolean(annonce.meuble),
    adresse: annonce.adresse ?? '',
    ville: annonce.ville ?? '',
    latitude: enChaine(annonce.latitude),
    longitude: enChaine(annonce.longitude),
    caracteristiques: [...(annonce.caracteristiques ?? [])],
    disponibilites: [...(annonce.disponibilites ?? [])],
  }
}

/** Nombre décimal saisi, ou NaN si la saisie n'en est pas un ("12,5" est accepté). */
function lireNombre(saisie) {
  const texte = enChaine(saisie).trim().replace(',', '.')
  return texte === '' ? NaN : Number(texte)
}

function verifierTexte(valeur, min, max) {
  const texte = valeur.trim()
  if (texte === '') return OBLIGATOIRE
  if (texte.length < min || texte.length > max) return `Doit contenir entre ${min} et ${max} caractères.`
  return null
}

function verifierStrictementPositif(saisie) {
  if (enChaine(saisie).trim() === '') return OBLIGATOIRE
  const nombre = lireNombre(saisie)
  if (!Number.isFinite(nombre)) return INVALIDE
  return nombre > 0 ? null : 'Doit être supérieur à 0.'
}

function verifierCoordonnee(saisie, min, max) {
  if (enChaine(saisie).trim() === '') return null // facultative
  const nombre = lireNombre(saisie)
  if (!Number.isFinite(nombre)) return INVALIDE
  return nombre >= min && nombre <= max ? null : `Doit être compris entre ${min} et ${max}.`
}

function verifierNbPieces(saisie) {
  if (enChaine(saisie).trim() === '') return OBLIGATOIRE
  const nombre = lireNombre(saisie)
  if (!Number.isInteger(nombre)) return 'Doit être un nombre entier.'
  return nombre >= 0 ? null : 'Doit être supérieur ou égal à 0.'
}

/**
 * Valide le formulaire avec les mêmes règles que le backend.
 *
 * @param {typeof VALEURS_VIDES} valeurs Valeurs saisies.
 * @returns {Record<string, string[]>} Erreurs par champ (objet vide si tout est valide).
 */
export function validerAnnonce(valeurs) {
  const verifications = {
    titre: verifierTexte(valeurs.titre, 5, 150),
    description: valeurs.description.trim() === '' ? OBLIGATOIRE : null,
    type_bien: valeurs.type_bien ? null : OBLIGATOIRE,
    transaction: valeurs.transaction ? null : OBLIGATOIRE,
    prix: verifierStrictementPositif(valeurs.prix),
    surface: verifierStrictementPositif(valeurs.surface),
    nb_pieces: verifierNbPieces(valeurs.nb_pieces),
    adresse: verifierTexte(valeurs.adresse, 1, 255),
    ville: verifierTexte(valeurs.ville, 1, 100),
    latitude: verifierCoordonnee(valeurs.latitude, -90, 90),
    longitude: verifierCoordonnee(valeurs.longitude, -180, 180),
  }
  const erreurs = {}
  for (const [champ, message] of Object.entries(verifications)) {
    if (message) erreurs[champ] = [message]
  }
  return erreurs
}

/**
 * Convertit des valeurs de formulaire (déjà validées) en corps JSON pour l'API.
 *
 * @param {typeof VALEURS_VIDES} valeurs Valeurs saisies.
 * @returns {object} Corps de POST / PUT (sans owner_id ni statut).
 */
export function versApi(valeurs) {
  const coordonnee = (saisie) => (enChaine(saisie).trim() === '' ? null : lireNombre(saisie))
  return {
    titre: valeurs.titre.trim(),
    description: valeurs.description.trim(),
    type_bien: valeurs.type_bien,
    transaction: valeurs.transaction,
    prix: lireNombre(valeurs.prix),
    surface: lireNombre(valeurs.surface),
    nb_pieces: lireNombre(valeurs.nb_pieces),
    meuble: valeurs.meuble,
    adresse: valeurs.adresse.trim(),
    ville: valeurs.ville.trim(),
    latitude: coordonnee(valeurs.latitude),
    longitude: coordonnee(valeurs.longitude),
    // Ordre fixe : cocher puis décocher une case ne compte pas comme une modification.
    caracteristiques: [...valeurs.caracteristiques].sort(),
  }
}

/**
 * Garde uniquement les champs dont la valeur a changé (pour un PUT partiel).
 *
 * @param {object} avant Corps API correspondant à l'annonce chargée.
 * @param {object} apres Corps API correspondant au formulaire soumis.
 * @returns {object} Champs modifiés (objet vide si rien n'a changé).
 */
export function champsModifies(avant, apres) {
  const modifications = {}
  for (const [champ, valeur] of Object.entries(apres)) {
    if (JSON.stringify(valeur) !== JSON.stringify(avant[champ])) modifications[champ] = valeur
  }
  return modifications
}
