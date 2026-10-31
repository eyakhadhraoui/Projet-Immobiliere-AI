import { api } from './client'

export async function listerDossiersLitige() {
  const { data } = await api.get('/dossiers-litige')
  return data.dossiers || []
}

export async function obtenirConfigurationLitige() {
  const { data } = await api.get('/dossiers-litige/configuration')
  return data
}

export async function creerDossierLitige(donnees) {
  const payload = typeof donnees === 'string' ? { nom: donnees } : donnees
  const { data } = await api.post('/dossiers-litige', payload)
  return data
}

export async function obtenirDossierLitige(id) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(id)}`)
  return data
}

export async function supprimerDossierLitige(id) {
  const { data } = await api.delete(`/dossiers-litige/${encodeURIComponent(id)}`)
  return data
}

export async function ajouterPieceLitige(id, fichier, metadonnees = {}) {
  const formulaire = new FormData()
  formulaire.append('fichier', fichier)
  Object.entries(metadonnees).forEach(([cle, valeur]) => {
    if (valeur !== undefined && valeur !== null) formulaire.append(cle, valeur)
  })
  const { data } = await api.post(`/dossiers-litige/${encodeURIComponent(id)}/documents`, formulaire)
  return data.document
}

export async function supprimerPieceLitige(caseId, documentId) {
  const { data } = await api.delete(`/dossiers-litige/${encodeURIComponent(caseId)}/documents/${documentId}`)
  return data
}

export async function modifierMetadonneesPiece(caseId, documentId, donnees) {
  const { data } = await api.patch(`/dossiers-litige/${encodeURIComponent(caseId)}/documents/${documentId}`, donnees)
  return data
}

export async function corrigerClassificationLitige(caseId, chunkId, donnees) {
  const { data } = await api.patch(`/dossiers-litige/${encodeURIComponent(caseId)}/classifications/${encodeURIComponent(chunkId)}`, donnees)
  return data
}

export async function obtenirPreuvesLitige(caseId, filtres = {}) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(caseId)}/evidence`, { params: filtres })
  return data
}

export async function obtenirChronologieLitige(caseId) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(caseId)}/timeline`)
  return data
}

export async function obtenirComptesLitige(caseId) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(caseId)}/accounts`)
  return data
}

export async function obtenirContradictionsLitige(caseId) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(caseId)}/contradictions`)
  return data
}

export async function obtenirPreuvesNonIdentifiees(caseId) {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(caseId)}/missing-evidence`)
  return data
}

export async function rechercherPreuvesLitige(caseId, question) {
  const { data } = await api.post(`/dossiers-litige/${encodeURIComponent(caseId)}/search`, { question })
  return data
}

export async function poserQuestionLitige(caseId, question) {
  const { data } = await api.post(`/dossiers-litige/${encodeURIComponent(caseId)}/questions`, { question })
  return data
}

export async function creerRapportLitige(caseId, format) {
  const { data } = await api.post(`/dossiers-litige/${encodeURIComponent(caseId)}/reports`, { format })
  return data
}

export async function telechargerRapportLitige(url) {
  const chemin = String(url).replace(/^\/api(?=\/)/, '')
  const { data } = await api.get(chemin, { responseType: 'blob' })
  return data
}

export async function obtenirRapportLitige(id, question = '') {
  const { data } = await api.get(`/dossiers-litige/${encodeURIComponent(id)}/rapport`, { params: { question } })
  return data
}
