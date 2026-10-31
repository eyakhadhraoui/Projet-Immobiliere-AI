import { api, nettoyerFiltres } from './annonces'

/** GET /api/annonces/<id>/historique — historique complet d'une annonce (même supprimée). */
export async function obtenirHistoriqueAnnonce(id) {
  const { data } = await api.get(`/annonces/${id}/historique`)
  return data.items
}

/** GET /api/historique — historique filtré et paginé. */
export async function listerHistorique(filtres = {}) {
  const { data } = await api.get('/historique', { params: nettoyerFiltres(filtres) })
  return data // { items, page, per_page, total }
}

/** GET /api/historique/<id> — détail d'une entrée d'historique. */
export async function obtenirHistoriqueDetail(id) {
  const { data } = await api.get(`/historique/${id}`)
  return data
}

/** POST /api/historique — créer une entrée ou note d'audit. */
export async function creerHistorique(donnees) {
  const { data } = await api.post('/historique', donnees)
  return data
}

/** DELETE /api/historique/<id> — supprimer une entrée d'audit. */
export async function supprimerHistorique(id) {
  const { data } = await api.delete(`/historique/${id}`)
  return data
}

/** GET /api/statistiques — chiffres du tableau de bord de l'espace propriétaire. */
export async function obtenirStatistiques() {
  const { data } = await api.get('/statistiques')
  return data
}
