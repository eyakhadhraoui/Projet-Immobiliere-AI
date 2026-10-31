import { obtenirAnnonce } from '../api/annonces'
import { useRequete } from './useRequete'

/**
 * Charge une annonce par son identifiant.
 *
 * @param {string|number} id Identifiant de l'annonce (paramètre d'URL).
 * @returns {{
 *   etat: 'chargement' | 'succes' | 'introuvable' | 'erreur',
 *   annonce: object | null,
 *   erreur: { message: string, champs: Record<string, string[]> } | null,
 *   reessayer: () => void,
 *   remplacerAnnonce: (maj: object | ((annonce: object) => object)) => void,
 * }}
 */
export function useAnnonce(id, inclureDisponibilites = false) {
  const { etat, donnees, erreur, reessayer, modifierDonnees } = useRequete(
    `annonce-${id}`,
    () => (inclureDisponibilites ? obtenirAnnonce(id, true) : obtenirAnnonce(id)),
  )
  return { etat, annonce: donnees, erreur, reessayer, remplacerAnnonce: modifierDonnees }
}
