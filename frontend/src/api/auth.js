import { api } from './client'

/** POST /api/auth/inscription — crée le compte et ouvre la session (cookies). */
export async function inscription(donnees) {
  const { data } = await api.post('/auth/inscription', donnees)
  return data
}

/** POST /api/auth/connexion — ouvre la session (cookies). */
export async function connexion(email, motDePasse) {
  const { data } = await api.post('/auth/connexion', { email, mot_de_passe: motDePasse })
  return data
}

/** Valide le code envoyé lors d'une connexion à très haut risque. */
export async function verifierConnexion(jeton, code) {
  const { data } = await api.post('/auth/verification-connexion', { jeton, code })
  return data
}

/** Enregistre la confirmation ou le signalement d'une connexion inhabituelle. */
export async function retourConnexion(evenementId, retour) {
  const { data } = await api.post(`/auth/connexions/${evenementId}/retour`, { retour })
  return data
}

/** Alerte inhabituelle en attente pour le compte connecté. */
export async function obtenirAlerteConnexion() {
  const { data } = await api.get('/auth/connexions/alerte')
  return data
}

/** Historique des connexions du compte connecté (sans IP ni empreinte). */
export async function obtenirHistoriqueConnexions() {
  const { data } = await api.get('/auth/connexions/historique')
  return data.items
}

/** POST /api/auth/deconnexion — efface les cookies de session. */
export async function deconnexion() {
  await api.post('/auth/deconnexion')
}

/**
 * Compte connecté, ou null si personne ne l'est (401).
 *
 * @returns {Promise<object | null>} Compte de l'utilisateur.
 */
export async function obtenirSession() {
  try {
    const { data } = await api.get('/auth/moi')
    return data
  } catch (error) {
    if (error?.response?.status === 401) return null
    throw error
  }
}

/** PUT /api/auth/moi — modifie le profil (seuls les champs envoyés). */
export async function modifierProfil(modifications) {
  const { data } = await api.put('/auth/moi', modifications)
  return data
}

/** PUT /api/auth/moi/mot-de-passe — les autres sessions sont fermées. */
export async function changerMotDePasse(ancien, nouveau) {
  const { data } = await api.put('/auth/moi/mot-de-passe', {
    ancien_mot_de_passe: ancien,
    nouveau_mot_de_passe: nouveau,
  })
  return data
}

/** POST /api/auth/moi/photo — multipart, champ "photo". */
export async function envoyerPhotoProfil(fichier) {
  const formulaire = new FormData()
  formulaire.append('photo', fichier)
  const { data } = await api.post('/auth/moi/photo', formulaire)
  return data
}

/** DELETE /api/auth/moi/photo. */
export async function retirerPhotoProfil() {
  const { data } = await api.delete('/auth/moi/photo')
  return data
}

/** DELETE /api/auth/moi — supprime le compte (et les annonces d'un propriétaire). */
export async function supprimerCompte(motDePasse) {
  await api.delete('/auth/moi', { data: { mot_de_passe: motDePasse } })
}
