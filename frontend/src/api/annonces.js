import axios from 'axios'
import { api } from './client'

// Instance partagée (CSRF et rafraîchissement de session) : voir api/client.js.
export { api }

/**
 * Retire les filtres vides (undefined, null, chaîne vide) et les espaces superflus.
 *
 * @param {Record<string, unknown>} filtres Filtres saisis.
 * @returns {Record<string, unknown>} Filtres à envoyer en paramètres de requête.
 */
export function nettoyerFiltres(filtres = {}) {
  const resultat = {}
  for (const [cle, valeur] of Object.entries(filtres)) {
    const propre = typeof valeur === 'string' ? valeur.trim() : valeur
    if (propre !== undefined && propre !== null && propre !== '') {
      resultat[cle] = propre
    }
  }
  return resultat
}

/** GET /api/annonces — liste filtrée et paginée. */
export async function listerAnnonces(filtres = {}) {
  const { data } = await api.get('/annonces', { params: nettoyerFiltres(filtres) })
  return data // { items, page, per_page, total }
}

const PAR_PAGE_MAX = 50 // limite de per_page côté backend (PER_PAGE_MAX)

/**
 * Charge toutes les annonces (toutes les pages), pour le tableau de l'espace propriétaire
 * où la recherche et le tri se font côté navigateur.
 *
 * @param {Record<string, unknown>} filtres Filtres de l'API (sans page ni per_page).
 * @returns {Promise<object[]>} Toutes les annonces correspondantes.
 */
export async function listerToutesLesAnnonces(filtres = {}) {
  const premiere = await listerAnnonces({ ...filtres, page: 1, per_page: PAR_PAGE_MAX })
  const nbPages = Math.ceil(premiere.total / PAR_PAGE_MAX)
  const suivantes = await Promise.all(
    Array.from({ length: Math.max(nbPages - 1, 0) }, (_, i) =>
      listerAnnonces({ ...filtres, page: i + 2, per_page: PAR_PAGE_MAX }),
    ),
  )
  return [premiere, ...suivantes].flatMap((page) => page.items)
}

/** GET /api/annonces/<id> — détail d'une annonce (avec ses photos). */
export async function obtenirAnnonce(id, inclureDisponibilites = false) {
  const { data } = await api.get(`/annonces/${id}`, {
    params: inclureDisponibilites ? { inclure_disponibilites: 'true' } : undefined,
  })
  return data
}

/** GET /api/annonces/<id>/creneaux — créneaux de visite proposés. */
export async function obtenirCreneauxVisite(id) {
  const { data } = await api.get(`/annonces/${id}/creneaux`)
  return data
}

/** PUT /api/annonces/<id>/disponibilites-visite — remplace les horaires proposés. */
export async function enregistrerDisponibilitesVisite(id, disponibilites) {
  const { data } = await api.put(`/annonces/${id}/disponibilites-visite`, { disponibilites })
  return data
}

/** GET /api/annonces/<id>/disponibilites-visite — horaires enregistrés. */
export async function obtenirDisponibilitesVisite(id) {
  const { data } = await api.get(`/annonces/${id}/disponibilites-visite`)
  return data
}

/** POST /api/annonces — création (l'annonce est créée en brouillon). */
export async function creerAnnonce(annonce) {
  const { data } = await api.post('/annonces', annonce)
  return data
}

/** POST /api/ia/description-annonce — génère ou améliore le texte du formulaire. */
export async function genererDescriptionAnnonce(donnees) {
  const { data } = await api.post('/ia/description-annonce', donnees)
  return data.description
}

/** PUT /api/annonces/<id> — modification (seuls les champs envoyés changent). */
export async function modifierAnnonce(id, modifications) {
  const { data } = await api.put(`/annonces/${id}`, modifications)
  return data
}

/** DELETE /api/annonces/<id> — suppression de l'annonce et de ses photos. */
export async function supprimerAnnonce(id) {
  const { data } = await api.delete(`/annonces/${id}`)
  return data
}

/** PATCH /api/annonces/<id>/statut — changement de statut. */
export async function changerStatut(id, statut, confirmationFiabilite = false) {
  const { data } = await api.patch(`/annonces/${id}/statut`, {
    statut,
    ...(confirmationFiabilite ? { confirmation_fiabilite: true } : {}),
  })
  return data
}

/** POST /api/annonces/<id>/fiabilite/revue — demande de revue humaine. */
export async function demanderRevueFiabilite(id) {
  const { data } = await api.post(`/annonces/${id}/fiabilite/revue`, {})
  return data
}

/** GET /api/annonces/<id>/fiabilite — dernier contrôle privé du propriétaire. */
export async function obtenirFiabiliteAnnonce(id) {
  const { data } = await api.get(`/annonces/${id}/fiabilite`)
  return data
}

/**
 * POST /api/annonces/<id>/photos — envoi multipart d'une ou plusieurs photos.
 *
 * @param {number|string} id Identifiant de l'annonce.
 * @param {File[]|FileList} fichiers Fichiers image (champ "photos").
 */
export async function ajouterPhotos(id, fichiers) {
  const formulaire = new FormData()
  for (const fichier of fichiers) {
    formulaire.append('photos', fichier)
  }
  const { data } = await api.post(`/annonces/${id}/photos`, formulaire)
  return data
}

/** DELETE /api/annonces/<id>/photos/<photo_id> — suppression d'une photo. */
export async function supprimerPhoto(id, photoId) {
  const { data } = await api.delete(`/annonces/${id}/photos/${photoId}`)
  return data
}

/** PATCH /api/annonces/<id>/photos/ordre — nouvel ordre des photos (liste d'identifiants). */
export async function reordonnerPhotos(id, ordre) {
  const { data } = await api.patch(`/annonces/${id}/photos/ordre`, { ordre })
  return data
}

const MESSAGES_PAR_STATUT = {
  400: 'La requête est invalide.',
  404: 'Ressource introuvable.',
  413: 'Les fichiers envoyés sont trop volumineux.',
  500: 'Le serveur a rencontré une erreur. Réessayez plus tard.',
  502: 'Le serveur est indisponible. Réessayez plus tard.',
  503: 'Le serveur est indisponible. Réessayez plus tard.',
  504: 'Le serveur met trop de temps à répondre. Réessayez plus tard.',
}

/** Transforme une valeur de "details" (liste, objet imbriqué ou texte) en liste de messages. */
function aplatirMessages(valeur) {
  if (Array.isArray(valeur)) return valeur.flatMap(aplatirMessages)
  if (valeur && typeof valeur === 'object') return Object.values(valeur).flatMap(aplatirMessages)
  return valeur === undefined || valeur === null ? [] : [String(valeur)]
}

/**
 * Convertit une erreur axios en message lisible pour l'interface.
 *
 * @param {unknown} error Erreur levée par axios.
 * @returns {{ message: string, champs: Record<string, string[]> }} Message général
 *   et, pour une erreur 400 de validation, les messages par champ.
 */
export function lireErreur(error) {
  if (axios.isCancel(error)) {
    return { message: 'La requête a été annulée.', champs: {} }
  }
  const reponse = error?.response
  if (!reponse) {
    return {
      message: "Impossible de contacter le serveur. Vérifiez votre connexion ou que l'API est démarrée.",
      champs: {},
    }
  }
  const { status, data } = reponse
  if (status === 400 && data?.error === 'validation') {
    const champs = {}
    for (const [champ, messages] of Object.entries(data.details ?? {})) {
      champs[champ] = aplatirMessages(messages)
    }
    return { message: 'Certaines données sont invalides.', champs }
  }
  if (typeof data?.message === 'string' && data.message) {
    return { message: data.message, champs: {} }
  }
  return {
    message: MESSAGES_PAR_STATUT[status] ?? `Erreur inattendue (code ${status}).`,
    champs: {},
  }
}
