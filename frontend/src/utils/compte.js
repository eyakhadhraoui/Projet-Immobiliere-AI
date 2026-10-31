import { erreursMotDePasse } from './motDePasse'

export const LIBELLES_ROLE = { client: 'Client', proprietaire: 'Propriétaire' }

const OBLIGATOIRE = 'Champ obligatoire.'
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Initiales affichées dans l'avatar quand il n'y a pas de photo (ex. « LR »).
 *
 * @param {{ prenom?: string, nom?: string }} utilisateur Compte.
 * @returns {string} Une ou deux lettres majuscules.
 */
export function initiales(utilisateur) {
  const lettres = [utilisateur?.prenom, utilisateur?.nom].map((mot) => (mot ?? '').trim().charAt(0)).join('')
  return (lettres || '?').toUpperCase()
}

/**
 * Adresse de retour après connexion, seulement si c'est une page interne du site
 * (empêche ?retour=https://site-malveillant… ou //site-malveillant…).
 *
 * @param {string | null} retour Valeur du paramètre ?retour=.
 * @returns {string | null} Chemin sûr, ou null.
 */
export function cheminRetourSur(retour) {
  if (!retour || !retour.startsWith('/') || retour.startsWith('//') || retour.startsWith('/\\')) return null
  return retour
}

/**
 * Lien vers la page de connexion qui ramène ensuite à la page demandée (ex. /connexion?retour=/espace).
 *
 * @param {string} chemin Page demandée (chemin + paramètres).
 * @returns {string} URL de la page de connexion.
 */
export function urlConnexion(chemin) {
  return `/connexion?retour=${encodeURIComponent(chemin).replace(/%2F/gi, '/')}`
}

function verifierTexte(valeur, max) {
  const texte = (valeur ?? '').trim()
  if (texte === '') return OBLIGATOIRE
  return texte.length > max ? `Doit contenir entre 1 et ${max} caractères.` : null
}

function verifierEmail(valeur) {
  const email = (valeur ?? '').trim()
  if (email === '') return OBLIGATOIRE
  return EMAIL.test(email) ? null : 'Adresse email invalide.'
}

function verifierTelephone(valeur) {
  const telephone = (valeur ?? '').trim()
  return telephone === '' || /^\+?[0-9 ]{8,20}$/.test(telephone) ? null : 'Numéro de téléphone invalide.'
}

function versErreurs(verifications) {
  const erreurs = {}
  for (const [champ, message] of Object.entries(verifications)) {
    if (Array.isArray(message)) erreurs[champ] = message
    else if (message) erreurs[champ] = [message]
  }
  return erreurs
}

/**
 * Valide le formulaire d'inscription (mêmes règles et messages que l'API).
 *
 * @param {object} valeurs Valeurs saisies (dont confirmation du mot de passe).
 * @returns {Record<string, string[]>} Erreurs par champ.
 */
export function validerInscription(valeurs) {
  return versErreurs({
    prenom: verifierTexte(valeurs.prenom, 100),
    nom: verifierTexte(valeurs.nom, 100),
    email: verifierEmail(valeurs.email),
    telephone: verifierTelephone(valeurs.telephone),
    role: valeurs.role ? null : 'Choisissez un type de compte.',
    mot_de_passe: erreursMotDePasse(valeurs.mot_de_passe),
    confirmation: valeurs.confirmation === valeurs.mot_de_passe ? null : 'Les deux mots de passe ne correspondent pas.',
  })
}

/**
 * Valide le formulaire du profil.
 *
 * @param {object} valeurs Valeurs saisies.
 * @returns {Record<string, string[]>} Erreurs par champ.
 */
export function validerProfil(valeurs) {
  const cin = (valeurs.cin_numero ?? '').trim()
  const naissance = valeurs.date_naissance ? new Date(valeurs.date_naissance) : null
  return versErreurs({
    prenom: verifierTexte(valeurs.prenom, 100),
    nom: verifierTexte(valeurs.nom, 100),
    email: verifierEmail(valeurs.email),
    telephone: verifierTelephone(valeurs.telephone),
    ville: (valeurs.ville ?? '').length > 100 ? 'Doit contenir entre 1 et 100 caractères.' : null,
    adresse: (valeurs.adresse ?? '').length > 255 ? 'Doit contenir entre 1 et 255 caractères.' : null,
    date_naissance: naissance && naissance > new Date() ? 'Ne peut pas être dans le futur.' : null,
    cin_numero: cin === '' || /^\d{8}$/.test(cin) ? null : 'La CIN doit contenir exactement 8 chiffres.',
  })
}

/**
 * Corps de PUT /api/auth/moi : uniquement les champs modifiés ; un champ vidé devient null.
 *
 * @param {object} utilisateur Compte actuel (réponse de l'API).
 * @param {object} valeurs Valeurs du formulaire.
 * @returns {object} Champs modifiés.
 */
export function modificationsProfil(utilisateur, valeurs) {
  const modifications = {}
  for (const champ of ['prenom', 'nom', 'email', 'telephone', 'date_naissance', 'ville', 'adresse']) {
    const nouvelle = (valeurs[champ] ?? '').trim()
    const actuelle = utilisateur[champ] ?? ''
    if (nouvelle !== actuelle) modifications[champ] = nouvelle === '' ? null : nouvelle
  }
  // La CIN n'est jamais renvoyée en clair : le champ sert uniquement à saisir un nouveau numéro.
  const cin = (valeurs.cin_numero ?? '').trim()
  if (cin !== '') modifications.cin_numero = cin
  return modifications
}
