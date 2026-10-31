import { useState } from 'react'
import { changerStatut, lireErreur } from '../api/annonces'
import { LIBELLES_STATUT } from '../utils/format'

/** Menu de changement de statut d'une annonce (PATCH /api/annonces/<id>/statut). */
export default function ChangementStatut({ annonce, onStatutChange }) {
  const [statut, setStatut] = useState(annonce.statut)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [message, setMessage] = useState(null)
  const [erreur, setErreur] = useState(null)

  async function soumettre(event) {
    event.preventDefault()
    setMessage(null)
    setErreur(null)
    setEnvoiEnCours(true)
    try {
      const annonceMaj = await changerStatut(annonce.id, statut)
      onStatutChange(annonceMaj)
      setMessage(`Statut modifié : ${LIBELLES_STATUT[annonceMaj.statut] ?? annonceMaj.statut}.`)
    } catch (error) {
      setErreur(lireErreur(error).message)
    } finally {
      setEnvoiEnCours(false)
    }
  }

  return (
    <form className="statut" onSubmit={soumettre}>
      <div className="champ">
        <label htmlFor="changement-statut">Statut de l'annonce</label>
        <div className="statut__ligne">
          <select
            id="changement-statut"
            value={statut}
            onChange={(event) => setStatut(event.target.value)}
            disabled={envoiEnCours}
          >
            {Object.entries(LIBELLES_STATUT).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
          <button type="submit" className="bouton" disabled={envoiEnCours || statut === annonce.statut}>
            {envoiEnCours ? 'Modification…' : 'Changer le statut'}
          </button>
        </div>
      </div>
      {message && (
        <p className="message-succes" role="status">
          {message}
        </p>
      )}
      {erreur && (
        <p className="champ__erreur" role="alert">
          {erreur}
        </p>
      )}
    </form>
  )
}
