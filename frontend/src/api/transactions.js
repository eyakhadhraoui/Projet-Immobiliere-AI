import { api } from './client'

/**
 * Appels API pour le module « Gestion des transactions ».
 */

export async function listerTransactions(params = {}) {
  const { data } = await api.get('/transactions', { params })
  return data
}

export async function obtenirTransaction(id) {
  const { data } = await api.get(`/transactions/${id}`)
  return data
}

export async function creerTransaction(donnees) {
  const { data } = await api.post('/transactions', donnees)
  return data
}

export async function modifierTransaction(id, donnees) {
  const { data } = await api.put(`/transactions/${id}`, donnees)
  return data
}

export async function supprimerTransaction(id) {
  const { data } = await api.delete(`/transactions/${id}`)
  return data
}

export async function ajouterPaiementTransaction(id, paiement) {
  const { data } = await api.post(`/transactions/${id}/paiements`, paiement)
  return data
}
