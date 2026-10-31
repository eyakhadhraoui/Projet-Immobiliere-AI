import { useCallback, useEffect, useEffectEvent, useState } from 'react'
import { lireErreur } from '../api/annonces'

/**
 * Charge des données depuis l'API et expose l'état du chargement.
 * La requête est relancée quand `cle` change ou après `reessayer()` ; une réponse arrivée
 * après un changement de clé est ignorée.
 *
 * @param {string} cle Identifie la requête (ex. JSON des paramètres).
 * @param {() => Promise<any>} charger Fonction qui appelle l'API.
 * @returns {{
 *   etat: 'chargement' | 'succes' | 'introuvable' | 'erreur',
 *   donnees: any,
 *   erreur: { message: string, champs: Record<string, string[]> } | null,
 *   reessayer: () => void,
 *   modifierDonnees: (maj: any | ((donnees: any) => any)) => void,
 * }}
 */
export function useRequete(cle, charger) {
  const [resultat, setResultat] = useState({ etat: 'chargement', donnees: null, erreur: null, requete: null })
  const [tentative, setTentative] = useState(0)
  const requete = `${cle}#${tentative}`
  const lancer = useEffectEvent(() => charger())

  useEffect(() => {
    let annule = false
    lancer()
      .then((donnees) => {
        if (!annule) setResultat({ etat: 'succes', donnees, erreur: null, requete })
      })
      .catch((error) => {
        if (annule) return
        const etat = error?.response?.status === 404 ? 'introuvable' : 'erreur'
        setResultat({ etat, donnees: null, erreur: lireErreur(error), requete })
      })
    return () => {
      annule = true
    }
  }, [requete])

  const reessayer = useCallback(() => setTentative((n) => n + 1), [])

  // Met à jour les données affichées après une action (statut, suppression…) sans recharger.
  const modifierDonnees = useCallback((maj) => {
    setResultat((precedent) => ({
      ...precedent,
      donnees: typeof maj === 'function' ? maj(precedent.donnees) : maj,
    }))
  }, [])

  if (resultat.requete !== requete) {
    return { etat: 'chargement', donnees: null, erreur: null, reessayer, modifierDonnees }
  }
  const { etat, donnees, erreur } = resultat
  return { etat, donnees, erreur, reessayer, modifierDonnees }
}
