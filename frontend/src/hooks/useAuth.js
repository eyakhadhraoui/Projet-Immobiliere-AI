import { useContext } from 'react'
import { ContexteAuth } from '../contexts/contexteAuth'

/**
 * Session de l'utilisateur.
 *
 * @returns {{
 *   utilisateur: object | null,
 *   chargement: boolean,
 *   connecter: (email: string, motDePasse: string) => Promise<object>,
 *   inscrire: (donnees: object) => Promise<object>,
 *   deconnecter: (quitter?: () => void) => Promise<void>,
 *   remplacerUtilisateur: (utilisateur: object | null) => void,
 *   terminerSession: (quitter?: () => void) => void,
 * }}
 */
export function useAuth() {
  const contexte = useContext(ContexteAuth)
  if (contexte === null) throw new Error('useAuth doit être utilisé dans <FournisseurAuth>.')
  return contexte
}
