import { api } from './client'

/**
 * Appels API pour le module « Gestion des réclamations ».
 */

export async function listerReclamations(params = {}) {
  const { data } = await api.get('/reclamations', { params })
  return data
}

export async function obtenirReclamation(id) {
  const { data } = await api.get(`/reclamations/${id}`)
  return data
}

export async function creerReclamation(donnees, fichiers = []) {
  if (fichiers.length) {
    const formulaire = new FormData()
    formulaire.append('donnees', JSON.stringify(donnees))
    fichiers.forEach((fichier) => formulaire.append('pieces_jointes', fichier))
    const { data } = await api.post('/reclamations', formulaire)
    return data
  }
  const { data } = await api.post('/reclamations', donnees)
  return data
}

export async function analyserAssistantReclamation(donnees) {
  const { data } = await api.post('/reclamations/assistant/analyser', donnees)
  return data
}

export async function ameliorerDescriptionReclamation(donnees) {
  const { data } = await api.post('/reclamations/assistant/ameliorer-description', donnees)
  return data
}

export async function modifierReclamation(id, donnees) {
  const { data } = await api.put(`/reclamations/${id}`, donnees)
  return data
}

export async function supprimerReclamation(id) {
  const { data } = await api.delete(`/reclamations/${id}`)
  return data
}

export async function ajouterMessageReclamation(id, message) {
  const { data } = await api.post(`/reclamations/${id}/messages`, { message })
  return data
}
