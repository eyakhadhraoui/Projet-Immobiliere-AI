import { api } from './client'

/**
 * Envoie une question ou une demande d'audit documentaire au chatbot RAG.
 *
 * @param {object} params
 * @param {string} params.message Question ou demande de l'utilisateur.
 * @param {string} [params.transaction] 'location', 'vente' ou 'general'.
 * @param {string[]} [params.elements_coches] Identifiants des pièces déjà fournies.
 * @param {string} [params.langue] 'fr' ou 'ar' (ou 'auto').
 * @returns {Promise<object>} { reponse, langue, transaction, sources, audit }.
 */
export async function envoyerMessageRag({ message, transaction = 'general', elements_coches = [], langue = 'auto' }) {
  const { data } = await api.post('/rag/chat', {
    message,
    transaction,
    elements_coches,
    langue: langue === 'auto' ? null : langue,
  })
  return data
}

/**
 * Récupère les checklists officielles de location et/ou vente.
 *
 * @param {string} [transaction] 'location', 'vente' ou vide pour les deux.
 * @returns {Promise<object>}
 */
export async function obtenirChecklists(transaction = '') {
  const url = transaction ? `/rag/checklists?transaction=${transaction}` : '/rag/checklists'
  const { data } = await api.get(url)
  return data
}

/**
 * Récupère les suggestions de questions fréquentes en français ou arabe.
 *
 * @param {string} [langue] 'fr' ou 'ar'.
 * @returns {Promise<Array<object>>}
 */
export async function obtenirSuggestions(langue = 'fr', transaction = 'general') {
  const params = new URLSearchParams({ langue, transaction })
  const { data } = await api.get(`/rag/suggestions?${params.toString()}`)
  return data.suggestions
}

/**
 * Analyse un document PDF ou texte pour détecter les pages manquantes,
 * champs vides, montants, CINs et complétude.
 *
 * @param {FormData|object} payload Fichier FormData ('fichier') ou objet JSON ('texte').
 * @returns {Promise<object>} Rapport d'analyse et d'audit.
 */
export async function analyserDocument(payload) {
  const estFormData = payload instanceof FormData
  const config = estFormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : {}
  const { data } = await api.post('/rag/analyser-document', payload, config)
  return data
}

/**
 * Génère un projet de contrat de bail ou promesse de vente selon le droit tunisien.
 *
 * @param {object} params
 * @returns {Promise<object>} { type_contrat, langue, contrat_markdown }.
 */
export async function genererContrat(params) {
  const { data } = await api.post('/rag/generer-contrat', params)
  return data
}

/** Liste le guide PDF public et les documents indexés de la session. */
export async function listerDocumentsRag() {
  const { data } = await api.get('/rag/documents')
  return data.documents || []
}

/** Envoie un PDF au backend pour extraction, découpage, embeddings et indexation. */
export async function importerDocumentRag(fichier) {
  const donnees = new FormData()
  donnees.append('fichier', fichier)
  const { data } = await api.post('/rag/documents', donnees)
  return data
}

/** Supprime un document privé de la base vectorielle. */
export async function supprimerDocumentRag(id) {
  const { data } = await api.delete(`/rag/documents/${encodeURIComponent(id)}`)
  return data
}

