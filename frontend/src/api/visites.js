import { api } from './client'

/**
 * Appels API pour le module « Gestion des visites ».
 */

export async function listerVisites(params = {}) {
  const { data } = await api.get('/visites', { params })
  return data
}

export async function rechercherVisites(criteres) {
  const { data } = await api.post('/visites/recherche', criteres)
  return data
}

export async function obtenirVisite(id) {
  const { data } = await api.get(`/visites/${id}`)
  return data
}

export async function creerVisite(donnees) {
  const { data } = await api.post('/visites', donnees)
  return data
}

export async function modifierVisite(id, donnees) {
  const { data } = await api.put(`/visites/${id}`, donnees)
  return data
}

export async function supprimerVisite(id) {
  const { data } = await api.delete(`/visites/${id}`)
  return data
}
