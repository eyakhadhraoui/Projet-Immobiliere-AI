import { lireErreur } from '../api/annonces'

/** Règles du backend (backend/app/services/photo_service.py et MAX_CONTENT_LENGTH). */
export const MAX_PHOTOS = 10
export const EXTENSIONS_AUTORISEES = ['jpg', 'jpeg', 'png', 'webp']
export const TAILLE_MAX_ENVOI = 5 * 1024 * 1024 // octets, pour l'ensemble d'une requête

/** Valeur de l'attribut accept du sélecteur de fichiers. */
export const ACCEPT_IMAGES = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'

function extension(nomFichier) {
  const point = nomFichier.lastIndexOf('.')
  return point === -1 ? '' : nomFichier.slice(point + 1).toLowerCase()
}

/** Ex. "4,2 Mo". */
export function formaterTaille(octets) {
  return `${(octets / (1024 * 1024)).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Mo`
}

/**
 * Vérifie une nouvelle sélection avant de l'ajouter aux photos en attente d'envoi.
 * La sélection est refusée en entier si elle contient un fichier invalide ou dépasse une limite,
 * pour que l'utilisateur sache exactement ce qui sera envoyé.
 *
 * @param {File[]} selection Fichiers choisis.
 * @param {number} nbExistantes Photos déjà enregistrées sur l'annonce.
 * @param {File[]} enAttente Fichiers déjà choisis mais pas encore envoyés.
 * @returns {string[]} Messages d'erreur (liste vide si la sélection est acceptée).
 */
export function verifierSelection(selection, nbExistantes, enAttente) {
  const erreurs = []

  const invalides = selection.filter((fichier) => !EXTENSIONS_AUTORISEES.includes(extension(fichier.name)))
  for (const fichier of invalides) {
    erreurs.push(`${fichier.name} : format non accepté (formats autorisés : ${EXTENSIONS_AUTORISEES.join(', ')}).`)
  }

  const restantes = MAX_PHOTOS - nbExistantes - enAttente.length
  if (selection.length > restantes) {
    erreurs.push(
      restantes > 0
        ? `Maximum ${MAX_PHOTOS} photos par annonce : vous pouvez encore en ajouter ${restantes}.`
        : `Maximum ${MAX_PHOTOS} photos par annonce : la limite est atteinte.`,
    )
  }

  const tailleTotale = [...enAttente, ...selection].reduce((total, fichier) => total + fichier.size, 0)
  if (tailleTotale > TAILLE_MAX_ENVOI) {
    erreurs.push(
      `Les photos à envoyer pèsent ${formaterTaille(tailleTotale)} : ${formaterTaille(TAILLE_MAX_ENVOI)} maximum par envoi.`,
    )
  }

  return erreurs
}

/**
 * Message affiché quand l'annonce est enregistrée mais que l'envoi des photos échoue.
 *
 * @param {string} debut Ex. "L'annonce a été créée".
 * @param {unknown} error Erreur axios de l'envoi des photos.
 * @returns {string} Message complet, avec le détail renvoyé par l'API.
 */
export function decrireEchecPhotos(debut, error) {
  const { message, champs } = lireErreur(error)
  const details = Object.values(champs).flat()
  const raison = details.length > 0 ? details.join(' ') : message
  return `${debut}, mais les photos n'ont pas pu être envoyées : ${raison} Vous pouvez les ajouter depuis « Modifier ».`
}
