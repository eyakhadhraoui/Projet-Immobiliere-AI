import { api } from './client'

/**
 * Appels API pour le module « Gestion des locations ».
 */

export async function listerLocations(params = {}) {
  const { data } = await api.get('/locations', { params })
  return data
}

export async function obtenirLocation(id) {
  const { data } = await api.get(`/locations/${id}`)
  return data
}

export async function creerLocation(donnees) {
  const { data } = await api.post('/locations', donnees)
  return data
}

export async function modifierLocation(id, donnees) {
  const { data } = await api.put(`/locations/${id}`, donnees)
  return data
}

export async function supprimerLocation(id) {
  const { data } = await api.delete(`/locations/${id}`)
  return data
}

export async function encaisserLoyerLocation(locationId, loyerId) {
  const { data } = await api.post(`/locations/${locationId}/loyers/${loyerId}/encaisser`)
  return data
}
