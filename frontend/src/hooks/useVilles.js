import { useEffect, useState } from 'react'
import { listerVilles } from '../api/ia'

// Une seule requête par chargement de page, partagée par tous les champs « Ville ».
let promesse = null

/** Réinitialise le cache (tests). */
export function viderCacheVilles() {
  promesse = null
}

/**
 * Villes proposées dans la liste déroulante des champs « Ville ».
 * En cas d'erreur (modèle absent, réseau), la liste est vide : la saisie libre reste possible.
 *
 * @returns {Array<{nom: string, nb_annonces: number}>} Villes connues.
 */
export default function useVilles() {
  const [villes, setVilles] = useState([])
  useEffect(() => {
    let actif = true
    promesse ??= Promise.resolve()
      .then(() => listerVilles())
      .catch(() => {
        promesse = null // nouvel essai au prochain affichage
        return []
      })
    promesse.then((liste) => actif && setVilles(Array.isArray(liste) ? liste : []))
    return () => {
      actif = false
    }
  }, [])
  return villes
}
