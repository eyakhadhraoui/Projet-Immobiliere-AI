import { LIBELLES_STATUT } from './format'

/** Colonnes triables du tableau « Mes annonces ». */
export const COLONNES_TRI = {
  titre: 'Titre',
  ville: 'Ville',
  prix: 'Prix',
  statut: 'Statut',
  updated_at: 'Mise à jour',
}

export const TRI_PAR_DEFAUT = { colonne: 'updated_at', sens: 'desc' }

const ORDRE_STATUTS = Object.keys(LIBELLES_STATUT)

/** Texte en minuscules sans accents, pour une recherche tolérante (« ariana » trouve « Ariana »). */
export function normaliser(texte) {
  return String(texte ?? '')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

/**
 * Filtre les annonces par texte (titre ou ville) et par statut.
 *
 * @param {object[]} annonces Annonces de l'API.
 * @param {{ recherche: string, statut: string }} criteres Statut '' = tous.
 * @returns {object[]} Annonces retenues.
 */
export function filtrerAnnonces(annonces, { recherche = '', statut = '' }) {
  const texte = normaliser(recherche)
  return annonces.filter(
    (annonce) =>
      (!statut || annonce.statut === statut) &&
      (!texte || normaliser(annonce.titre).includes(texte) || normaliser(annonce.ville).includes(texte)),
  )
}

const COMPARATEURS = {
  titre: (a, b) => a.titre.localeCompare(b.titre, 'fr', { sensitivity: 'base' }),
  ville: (a, b) => a.ville.localeCompare(b.ville, 'fr', { sensitivity: 'base' }),
  prix: (a, b) => a.prix - b.prix,
  statut: (a, b) => ORDRE_STATUTS.indexOf(a.statut) - ORDRE_STATUTS.indexOf(b.statut),
  updated_at: (a, b) => new Date(a.updated_at) - new Date(b.updated_at),
}

/**
 * Trie une copie des annonces (à égalité, l'ordre d'identifiant décroissant départage).
 *
 * @param {object[]} annonces Annonces à trier.
 * @param {{ colonne: string, sens: 'asc' | 'desc' }} tri Colonne de COLONNES_TRI et sens.
 * @returns {object[]} Nouvelle liste triée.
 */
export function trierAnnonces(annonces, { colonne, sens }) {
  const comparer = COMPARATEURS[colonne] ?? COMPARATEURS.updated_at
  const facteur = sens === 'asc' ? 1 : -1
  return [...annonces].sort((a, b) => facteur * comparer(a, b) || b.id - a.id)
}
