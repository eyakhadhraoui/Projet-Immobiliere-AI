import { useState } from 'react'
import { changerMotDePasse } from '../api/auth'
import { lireErreur } from '../api/annonces'
import { useAuth } from '../hooks/useAuth'
import { erreursMotDePasse } from '../utils/motDePasse'
import Champ from './Champ'
import ChampMotDePasse from './ChampMotDePasse'
import ForceMotDePasse from './ForceMotDePasse'

const VIDE = { ancien: '', nouveau: '', confirmation: '' }

/** Changement du mot de passe (ancien obligatoire) ; les autres sessions ouvertes sont fermées par l'API. */
export default function ProfilMotDePasse() {
  const { remplacerUtilisateur } = useAuth()
  const [valeurs, setValeurs] = useState(VIDE)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)

  function modifier(event) {
    const { name, value } = event.target
    setValeurs((v) => ({ ...v, [name]: value }))
    setErreurs((e) => ({ ...e, [name]: undefined }))
    setMessage(null)
  }

  async function soumettre(event) {
    event.preventDefault()
    setMessage(null)
    const erreursClient = {}
    if (!valeurs.ancien) erreursClient.ancien = ['Champ obligatoire.']
    const problemes = erreursMotDePasse(valeurs.nouveau)
    if (problemes) erreursClient.nouveau = problemes
    else if (valeurs.nouveau === valeurs.ancien) erreursClient.nouveau = ["Doit être différent de l'ancien mot de passe."]
    if (valeurs.confirmation !== valeurs.nouveau) erreursClient.confirmation = ['Les deux mots de passe ne correspondent pas.']
    setErreurs(erreursClient)
    if (Object.keys(erreursClient).length > 0) return

    setEnvoiEnCours(true)
    try {
      remplacerUtilisateur(await changerMotDePasse(valeurs.ancien, valeurs.nouveau))
      setValeurs(VIDE)
      setMessage('Mot de passe modifié. Vos autres sessions ont été fermées.')
    } catch (error) {
      const { message: texte, champs } = lireErreur(error)
      setErreurs({
        ancien: champs.ancien_mot_de_passe,
        nouveau: champs.nouveau_mot_de_passe,
        ...(Object.keys(champs).length === 0 ? { ancien: [texte] } : {}),
      })
    } finally {
      setEnvoiEnCours(false)
    }
  }

  return (
    <section className="panneau profil__section" aria-labelledby="titre-mot-de-passe">
      <h2 id="titre-mot-de-passe">Mot de passe</h2>
      <form className="formulaire formulaire--nu" onSubmit={soumettre} noValidate aria-busy={envoiEnCours}>
        <Champ nom="ancien" libelle="Mot de passe actuel" erreurs={erreurs.ancien}>
          {(aria) => <ChampMotDePasse aria={aria} value={valeurs.ancien} onChange={modifier} autoComplete="current-password" />}
        </Champ>
        <Champ nom="nouveau" libelle="Nouveau mot de passe" erreurs={erreurs.nouveau}>
          {(aria) => (
            <ChampMotDePasse
              aria={{ ...aria, 'aria-describedby': [aria['aria-describedby'], 'force-nouveau'].filter(Boolean).join(' ') }}
              value={valeurs.nouveau}
              onChange={modifier}
              autoComplete="new-password"
            />
          )}
        </Champ>
        <ForceMotDePasse motDePasse={valeurs.nouveau} id="force-nouveau" />
        <Champ nom="confirmation" libelle="Confirmer le nouveau mot de passe" erreurs={erreurs.confirmation}>
          {(aria) => <ChampMotDePasse aria={aria} value={valeurs.confirmation} onChange={modifier} autoComplete="new-password" />}
        </Champ>
        <div className="formulaire__actions">
          <button type="submit" className="bouton bouton--principal" disabled={envoiEnCours}>
            {envoiEnCours ? 'Modification…' : 'Changer le mot de passe'}
          </button>
        </div>
        {message && (
          <p className="message-succes" role="status">
            {message}
          </p>
        )}
      </form>
    </section>
  )
}
