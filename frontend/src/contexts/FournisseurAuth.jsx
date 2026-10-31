import { startTransition, useCallback, useEffect, useMemo, useState } from 'react'
import { connexion, deconnexion, inscription, obtenirAlerteConnexion, obtenirSession, retourConnexion, verifierConnexion } from '../api/auth'
import { surFinDeSession } from '../api/client'
import { ContexteAuth } from './contexteAuth'

/**
 * Fournit l'utilisateur connecté à toute l'application.
 *
 * Au démarrage, la session est lue auprès de l'API (cookies httpOnly) ; rien n'est stocké côté navigateur.
 * utilisateurInitial : session déjà connue (null = visiteur) ; dans ce cas, aucune requête au démarrage.
 */
export default function FournisseurAuth({ children, utilisateurInitial }) {
  const sessionConnue = utilisateurInitial !== undefined
  const [etat, setEtat] = useState({
    chargement: !sessionConnue,
    utilisateur: sessionConnue ? utilisateurInitial : null,
  })
  const [alerteConnexion, setAlerteConnexion] = useState(null)

  useEffect(() => {
    if (sessionConnue) return undefined
    let annule = false
    obtenirSession()
      .then((utilisateur) => {
        if (!annule) {
          setEtat({ chargement: false, utilisateur })
          if (utilisateur && typeof obtenirAlerteConnexion === 'function') Promise.resolve()
            .then(() => obtenirAlerteConnexion())
            .then((alerte) => { if (!annule) setAlerteConnexion(alerte) })
            .catch(() => {})
        }
      })
      .catch(() => {
        if (!annule) setEtat({ chargement: false, utilisateur: null })
      })
    return () => {
      annule = true
    }
  }, [sessionConnue])

  // Session perdue (rafraîchissement impossible) : l'interface repasse en mode visiteur.
  useEffect(() => surFinDeSession(() => setEtat({ chargement: false, utilisateur: null })), [])

  const remplacerUtilisateur = useCallback((utilisateur) => {
    setEtat({ chargement: false, utilisateur })
  }, [])

  /**
   * Ferme la session puis appelle quitter (ex. navigate('/')) dans la même transition que l'effacement :
   * les navigations de React Router sont des transitions ; sans cela, la page protégée en cours verrait
   * d'abord un visiteur et redirigerait vers la connexion.
   */
  const terminerSession = useCallback((quitter) => {
    startTransition(() => {
      quitter?.()
      setEtat({ chargement: false, utilisateur: null })
    })
  }, [])

  const connecter = useCallback(async (email, motDePasse) => {
    const resultat = await connexion(email, motDePasse)
    if (resultat.verification_requise) return resultat
    const { alerte_connexion: alerte, ...utilisateur } = resultat
    setAlerteConnexion(alerte ?? null)
    setEtat({ chargement: false, utilisateur })
    return utilisateur
  }, [])

  const verifierCodeConnexion = useCallback(async (jeton, code) => {
    const utilisateur = await verifierConnexion(jeton, code)
    setAlerteConnexion(null)
    setEtat({ chargement: false, utilisateur })
    return utilisateur
  }, [])

  const traiterAlerteConnexion = useCallback(async (retour) => {
    if (!alerteConnexion) return
    await retourConnexion(alerteConnexion.evenement_id, retour)
    setAlerteConnexion(null)
    if (retour === 'refusee') terminerSession()
  }, [alerteConnexion, terminerSession])

  const inscrire = useCallback(async (donnees) => {
    const utilisateur = await inscription(donnees)
    setEtat({ chargement: false, utilisateur })
    return utilisateur
  }, [])

  const deconnecter = useCallback(async (quitter) => {
    try {
      await deconnexion()
    } finally {
      terminerSession(quitter)
    }
  }, [terminerSession])

  const valeur = useMemo(
    () => ({ ...etat, alerteConnexion, connecter, verifierCodeConnexion, traiterAlerteConnexion,
      inscrire, deconnecter, remplacerUtilisateur, terminerSession }),
    [etat, alerteConnexion, connecter, verifierCodeConnexion, traiterAlerteConnexion,
      inscrire, deconnecter, remplacerUtilisateur, terminerSession],
  )

  return <ContexteAuth.Provider value={valeur}>{children}</ContexteAuth.Provider>
}
