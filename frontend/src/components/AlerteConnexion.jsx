import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'

/** Demande à l'utilisateur de confirmer une connexion que l'analyse a jugée inhabituelle. */
export default function AlerteConnexion() {
  const { alerteConnexion, traiterAlerteConnexion } = useAuth()
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  if (!alerteConnexion) return null

  async function repondre(retour) {
    setEnCours(true)
    setErreur('')
    try {
      await traiterAlerteConnexion(retour)
    } catch {
      setErreur('Votre réponse n’a pas pu être enregistrée. Réessayez.')
      setEnCours(false)
    }
  }

  return (
    <aside className="alerte-connexion" role="alert" aria-live="assertive">
      <div>
        <strong>Connexion inhabituelle</strong>
        <p>{alerteConnexion.message}</p>
        {erreur && <p className="alerte-connexion__erreur">{erreur}</p>}
      </div>
      <div className="alerte-connexion__actions">
        <button type="button" className="bouton bouton--petit" disabled={enCours} onClick={() => repondre('confirmee')}>
          C’était moi
        </button>
        <button type="button" className="bouton bouton--petit bouton--danger" disabled={enCours} onClick={() => repondre('refusee')}>
          Ce n’était pas moi
        </button>
      </div>
    </aside>
  )
}
