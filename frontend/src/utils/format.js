const formateurNombre = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 3 })

/** Espace insécable (U+00A0) : empêche "1 200 TND" d'être coupé en fin de ligne. */
export const ESPACE_INSECABLE = String.fromCharCode(0xa0)

/** Libellés français des valeurs renvoyées par l'API. */
export const LIBELLES_TYPE_BIEN = {
  appartement: 'Appartement',
  maison: 'Maison',
  studio: 'Studio',
  villa: 'Villa',
  residence: 'Résidence',
}

export const LIBELLES_TRANSACTION = {
  vente: 'Vente',
  location: 'Location',
}

export const LIBELLES_STATUT = {
  brouillon: 'Brouillon',
  en_attente: 'En attente',
  publiee: 'Publiée',
  louee: 'Louée',
  vendue: 'Vendue',
}

/**
 * Formate un nombre à la française avec des espaces insécables (ex. 1 200).
 *
 * @param {number} valeur Nombre à formater.
 * @returns {string} Nombre formaté.
 */
export function formaterNombre(valeur) {
  // Intl utilise une espace fine insécable (U+202F) : on la remplace par une espace insécable classique.
  return formateurNombre.format(valeur).replace(/\s/g, ESPACE_INSECABLE)
}

/**
 * Formate un prix en dinars tunisiens, suivi de "/mois" pour une location.
 *
 * @param {number} prix Montant en dinars.
 * @param {string} transaction "vente" ou "location".
 * @returns {string} Ex. "1 200 TND/mois".
 */
export function formaterPrix(prix, transaction) {
  const suffixe = transaction === 'location' ? '/mois' : ''
  return `${formaterNombre(prix)}${ESPACE_INSECABLE}TND${suffixe}`
}

/** Ex. "85 m²". */
export function formaterSurface(surface) {
  return `${formaterNombre(surface)}${ESPACE_INSECABLE}m²`
}

/** Ex. "1 pièce", "3 pièces". */
export function formaterPieces(nbPieces) {
  return `${nbPieces}${ESPACE_INSECABLE}${nbPieces > 1 ? 'pièces' : 'pièce'}`
}

/** Badge public des cartes : la transaction parle plus au client que le statut. */
export const LIBELLES_TRANSACTION_PUBLIC = {
  vente: 'À vendre',
  location: 'À louer',
}

const formateurDate = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' })
const formateurJour = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
const formateurHeure = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })

/** Ex. "21/10/2026 à 12:50" (heure locale du navigateur) ; chaîne vide si la date est invalide. */
export function formaterDateHeure(dateIso) {
  const date = new Date(dateIso ?? '')
  if (Number.isNaN(date.getTime())) return ''
  return `${formateurJour.format(date)} à ${formateurHeure.format(date)}`
}

/** Ex. "21 octobre 2026" ; chaîne vide si la date est absente ou invalide. */
export function formaterDate(dateIso) {
  const date = new Date(dateIso ?? '')
  return Number.isNaN(date.getTime()) ? '' : formateurDate.format(date)
}
