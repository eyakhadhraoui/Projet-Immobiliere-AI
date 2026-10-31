import { listerAnnonces } from '../api/annonces'
import { useRequete } from './useRequete'

/**
 * Charge la liste des annonces pour des paramètres donnés.
 *
 * @param {Record<string, unknown>} params Filtres, page et per_page.
 * @returns {{
 *   etat: 'chargement' | 'succes' | 'erreur',
 *   donnees: { items: object[], page: number, per_page: number, total: number } | null,
 *   erreur: { message: string, champs: Record<string, string[]> } | null,
 *   reessayer: () => void,
 * }}
 */
export function useAnnonces(params) {
  // Clé stable : l'objet params est recréé à chaque rendu, sa sérialisation non.
  const cle = JSON.stringify(params)
  const { etat, donnees, erreur, reessayer } = useRequete(cle, () => listerAnnonces(JSON.parse(cle)))
  return { etat, donnees, erreur, reessayer }
}
