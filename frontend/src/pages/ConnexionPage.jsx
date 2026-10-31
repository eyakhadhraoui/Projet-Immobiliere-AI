import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { lireErreur } from '../api/annonces'
import Champ from '../components/Champ'
import ChampMotDePasse from '../components/ChampMotDePasse'
import { useAuth } from '../hooks/useAuth'
import { cheminRetourSur } from '../utils/compte'

/** Destination après connexion : la page demandée, sinon l'espace (propriétaire) ou l'accueil (client). */
function destination(retour, utilisateur) {
  return retour ?? (utilisateur.role === 'proprietaire' ? '/espace' : '/')
}

/** Page de connexion ; ?retour=/chemin ramène à la page demandée après connexion. */
export default function ConnexionPage() {
  const { utilisateur, connecter, verifierCodeConnexion } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const retour = cheminRetourSur(searchParams.get('retour'))
  const [valeurs, setValeurs] = useState({ email: '', mot_de_passe: '' })
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [verification, setVerification] = useState(null)
  const [codeVerification, setCodeVerification] = useState('')

  if (utilisateur && !envoiEnCours) return <Navigate to={destination(retour, utilisateur)} replace />

  function modifier(event) {
    const { name, value } = event.target
    setValeurs((v) => ({ ...v, [name]: value }))
    setErreurs((e) => ({ ...e, [name]: undefined }))
  }

  async function soumettre(event) {
    event.preventDefault()
    const manquants = {}
    if (!valeurs.email.trim()) manquants.email = ['Champ obligatoire.']
    if (!valeurs.mot_de_passe) manquants.mot_de_passe = ['Champ obligatoire.']
    setErreurs(manquants)
    setErreurGenerale(null)
    if (Object.keys(manquants).length > 0) return

    setEnvoiEnCours(true)
    try {
      const compte = await connecter(valeurs.email, valeurs.mot_de_passe)
      if (compte.verification_requise) {
        setVerification(compte)
        setValeurs((v) => ({ ...v, mot_de_passe: '' }))
        setEnvoiEnCours(false)
        return
      }
      navigate(destination(retour, compte), { replace: true })
    } catch (error) {
      // 401 : même message que l'email existe ou non ; 429 : blocage temporaire.
      setErreurGenerale(lireErreur(error).message)
      setValeurs((v) => ({ ...v, mot_de_passe: '' }))
      setEnvoiEnCours(false)
    }
  }

  async function validerCode(event) {
    event.preventDefault()
    setErreurGenerale(null)
    if (!/^\d{6}$/.test(codeVerification)) {
      setErreurGenerale('Saisissez le code à six chiffres reçu par e-mail.')
      return
    }
    setEnvoiEnCours(true)
    try {
      const compte = await verifierCodeConnexion(verification.jeton_verification, codeVerification)
      navigate(destination(retour, compte), { replace: true })
    } catch (error) {
      setErreurGenerale(lireErreur(error).message)
      setCodeVerification('')
      setEnvoiEnCours(false)
    }
  }

  return (
    <section className="page page--auth">
      <div className="carte-auth">
        <h1>Connexion</h1>
        <p className="page__intro">Accédez à votre compte pour gérer votre profil et vos annonces.</p>
        <form className="formulaire" onSubmit={soumettre} noValidate aria-busy={envoiEnCours}>
          {erreurGenerale && (
            <p className="etat etat--erreur formulaire__alerte" role="alert">
              {erreurGenerale}
            </p>
          )}
          {verification ? (
            <>
              <p role="status">{verification.message}</p>
              <label htmlFor="code-verification">Code reçu par e-mail</label>
              <input id="code-verification" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                value={codeVerification} onChange={(event) => setCodeVerification(event.target.value.replace(/\D/g, '').slice(0, 6))} />
              <button type="button" className="bouton bouton--principal bouton--large" disabled={envoiEnCours}
                onClick={validerCode}>
                {envoiEnCours ? 'Vérification…' : 'Vérifier et se connecter'}
              </button>
            </>
          ) : (
            <>
              <Champ nom="email" libelle="Email" erreurs={erreurs.email}>
                {(aria) => <input {...aria} type="email" autoComplete="email" value={valeurs.email} onChange={modifier} />}
              </Champ>
              <Champ nom="mot_de_passe" libelle="Mot de passe" erreurs={erreurs.mot_de_passe}>
                {(aria) => (
                  <ChampMotDePasse aria={aria} value={valeurs.mot_de_passe} onChange={modifier} autoComplete="current-password" />
                )}
              </Champ>
              <button type="submit" className="bouton bouton--principal bouton--large" disabled={envoiEnCours}>
                {envoiEnCours ? 'Connexion…' : 'Se connecter'}
              </button>
            </>
          )}
        </form>
        <p className="carte-auth__pied">
          Pas encore de compte ?{' '}
          <Link to={retour ? `/inscription?retour=${encodeURIComponent(retour)}` : '/inscription'}>Créer un compte</Link>
        </p>
      </div>
    </section>
  )
}
