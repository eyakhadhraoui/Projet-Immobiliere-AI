import { createContext } from 'react'

/**
 * Contexte d'authentification : { utilisateur, chargement, connecter, inscrire, deconnecter, remplacerUtilisateur }.
 * Fourni par FournisseurAuth, lu avec useAuth().
 */
export const ContexteAuth = createContext(null)
