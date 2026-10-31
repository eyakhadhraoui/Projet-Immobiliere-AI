import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supprimerCompte } from '../api/auth'
import { lireErreur } from '../api/annonces'
import { useAuth } from '../hooks/useAuth'
import Champ from './Champ'
import ChampMotDePasse from './ChampMotDePasse'
import FenetreConfirmation from './FenetreConfirmation'

/** Zone de danger : suppression définitive du compte (mot de passe, puis fenêtre de confirmation). */
export default function ProfilZoneDanger() {
  const { utilisateur, terminerSession } = useAuth()
  const navigate = useNavigate()
  const [motDePasse, setMotDePasse] = useState('')
  const [erreur, setErreur] = useState(null)
  const [confirmation, setConfirmation] = useState(false)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const proprietaire = utilisateur.role === 'proprietaire'

  function demander(event) {
    event.preventDefault()
    if (!motDePasse) {
      setErreur(['Saisissez votre mot de passe pour confirmer.'])
      return
    }
    setErreur(null)
    setConfirmation(true)
  }

  async function supprimer() {
    setEnvoiEnCours(true)
    try {
      await supprimerCompte(motDePasse)
      terminerSession(() => navigate('/', { replace: true, state: { succes: 'Votre compte a été supprimé.' } }))
    } catch (error) {
      const { message, champs } = lireErreur(error)
      setErreur(champs.mot_de_passe ?? [message])
      setConfirmation(false)
      setEnvoiEnCours(false)
    }
  }

  return (
    <section className="panneau profil__section zone-danger" aria-labelledby="titre-zone-danger">
      <h2 id="titre-zone-danger">Zone de danger</h2>
      <p>
        La suppression du compte est <strong>définitive</strong>
        {proprietaire ? ' : votre profil, votre photo et toutes vos annonces (avec leurs photos) seront supprimés.' : ' : votre profil et votre photo seront supprimés.'}
      </p>
      <form className="formulaire formulaire--nu" onSubmit={demander} noValidate>
        <Champ nom="mot_de_passe_suppression" libelle="Mot de passe" erreurs={erreur ?? undefined}>
          {(aria) => (
            <ChampMotDePasse aria={aria} value={motDePasse} autoComplete="current-password"
              onChange={(event) => { setMotDePasse(event.target.value); setErreur(null) }} />
          )}
        </Champ>
        <div className="formulaire__actions">
          <button type="submit" className="bouton bouton--danger">
            Supprimer mon compte
          </button>
        </div>
      </form>

      {confirmation && (
        <FenetreConfirmation
          titre="Supprimer définitivement votre compte ?"
          message={
            proprietaire
              ? 'Votre compte, votre photo de profil et toutes vos annonces, avec leurs photos, seront supprimés. Cette action est irréversible.'
              : 'Votre compte et votre photo de profil seront supprimés. Cette action est irréversible.'
          }
          libelleConfirmer="Supprimer mon compte"
          libelleEnCours="Suppression…"
          enCours={envoiEnCours}
          onConfirmer={supprimer}
          onAnnuler={() => setConfirmation(false)}
        />
      )}
    </section>
  )
}
