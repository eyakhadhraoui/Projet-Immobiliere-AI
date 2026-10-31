import { useState } from 'react'
import { modifierProfil } from '../api/auth'
import { lireErreur } from '../api/annonces'
import { useAuth } from '../hooks/useAuth'
import { modificationsProfil, validerProfil } from '../utils/compte'
import Champ from './Champ'

function valeursDe(utilisateur) {
  return {
    prenom: utilisateur.prenom ?? '',
    nom: utilisateur.nom ?? '',
    email: utilisateur.email ?? '',
    telephone: utilisateur.telephone ?? '',
    date_naissance: utilisateur.date_naissance ?? '',
    ville: utilisateur.ville ?? '',
    adresse: utilisateur.adresse ?? '',
    cin_numero: '', // la CIN n'est jamais renvoyée en clair : ce champ sert à en saisir une nouvelle
  }
}

/** Informations personnelles : consultation et modification (seuls les champs modifiés sont envoyés). */
export default function ProfilInformations() {
  const { utilisateur, remplacerUtilisateur } = useAuth()
  const [valeurs, setValeurs] = useState(() => valeursDe(utilisateur))
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [erreurGenerale, setErreurGenerale] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)

  function modifier(event) {
    const { name, value } = event.target
    setValeurs((v) => ({ ...v, [name]: value }))
    setErreurs((e) => ({ ...e, [name]: undefined }))
    setMessage(null)
  }

  async function soumettre(event) {
    event.preventDefault()
    setErreurGenerale(null)
    setMessage(null)
    const erreursClient = validerProfil(valeurs)
    setErreurs(erreursClient)
    if (Object.keys(erreursClient).length > 0) return

    const modifications = modificationsProfil(utilisateur, valeurs)
    if (Object.keys(modifications).length === 0) {
      setMessage('Aucune modification à enregistrer.')
      return
    }
    setEnvoiEnCours(true)
    try {
      const misAJour = await modifierProfil(modifications)
      remplacerUtilisateur(misAJour)
      setValeurs(valeursDe(misAJour))
      setMessage('Vos informations ont été enregistrées.')
    } catch (error) {
      const { message: texte, champs } = lireErreur(error)
      if (error?.response?.status === 409) {
        setErreurs(texte.includes('CIN') ? { cin_numero: [texte] } : { email: [texte] })
      } else {
        setErreurs(champs)
        setErreurGenerale(texte)
      }
    } finally {
      setEnvoiEnCours(false)
    }
  }

  const champTexte = (nom, libelle, options = {}) => (
    <Champ nom={nom} libelle={libelle} erreurs={erreurs[nom]} aide={options.aide}>
      {(aria) => <input {...aria} type={options.type ?? 'text'} autoComplete={options.autoComplete}
        inputMode={options.inputMode} value={valeurs[nom]} onChange={modifier} />}
    </Champ>
  )

  return (
    <section className="panneau profil__section" aria-labelledby="titre-informations">
      <h2 id="titre-informations">Informations personnelles</h2>
      <form className="formulaire formulaire--nu" onSubmit={soumettre} noValidate aria-busy={envoiEnCours}>
        {erreurGenerale && (
          <p className="etat etat--erreur formulaire__alerte" role="alert">
            {erreurGenerale}
          </p>
        )}
        <div className="formulaire__grille formulaire__grille--nue">
          {champTexte('prenom', 'Prénom *', { autoComplete: 'given-name' })}
          {champTexte('nom', 'Nom *', { autoComplete: 'family-name' })}
          {champTexte('email', 'Email *', { type: 'email', autoComplete: 'email' })}
          {champTexte('telephone', 'Téléphone', { type: 'tel', autoComplete: 'tel' })}
          {champTexte('date_naissance', 'Date de naissance', { type: 'date', autoComplete: 'bday' })}
          {champTexte('ville', 'Ville', { autoComplete: 'address-level2' })}
        </div>
        {champTexte('adresse', 'Adresse', { autoComplete: 'street-address' })}
        {champTexte('cin_numero', 'Nouveau numéro de CIN', {
          inputMode: 'numeric',
          aide: utilisateur.cin_numero
            ? `CIN enregistrée : ${utilisateur.cin_numero}. Laissez vide pour la conserver.`
            : 'Aucune CIN enregistrée (8 chiffres).',
        })}
        <div className="formulaire__actions">
          <button type="submit" className="bouton bouton--principal" disabled={envoiEnCours}>
            {envoiEnCours ? 'Enregistrement…' : 'Enregistrer'}
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
