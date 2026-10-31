import { api } from './client'

/**
 * POST /api/ia/estimation-prix — estimation du prix (propriétaire connecté).
 *
 * @param {object} bien type_bien, transaction, ville, surface, nb_pieces, meuble, caracteristiques
 *   et, facultatif, nb_sdb (salles de bain, utilisé seulement pour l'estimation).
 * @returns {Promise<object>} { prix_estime, fourchette, devise, transaction, confiance, facteurs,
 *   modele: { nom, mape_test, entraine_le, source }, avertissement }.
 */
export async function estimerPrix(bien) {
  const { data } = await api.post('/ia/estimation-prix', bien)
  return data
}

/**
 * GET /api/ia/villes — villes connues du modèle d'estimation (public), pour la liste déroulante « Ville ».
 *
 * @returns {Promise<Array<{nom: string, nb_annonces: number}>>} Villes triées par nom (vide sans modèle).
 */
export async function listerVilles() {
  const { data } = await api.get('/ia/villes')
  return data.villes
}

/** Analyse une annonce du propriétaire connecté (Isolation Forest, avis uniquement). */
export async function analyserAnomalieAnnonce(id) {
  const { data } = await api.post(`/ia/annonces/${id}/analyser-anomalie`)
  return data
}

/** Indique au propriétaire quel moteur de contrôle de fiabilité est disponible. */
export async function obtenirEtatFiabilite() {
  const { data } = await api.get('/ia/fiabilite/etat')
  return data
}
