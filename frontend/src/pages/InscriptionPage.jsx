import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { lireErreur } from '../api/annonces'
import Champ from '../components/Champ'
import ChampMotDePasse from '../components/ChampMotDePasse'
import ForceMotDePasse from '../components/ForceMotDePasse'
import { useAuth } from '../hooks/useAuth'
import { cheminRetourSur, validerInscription } from '../utils/compte'

const VALEURS_VIDES = { prenom: '', nom: '', email: '', telephone: '', ville: '', role: '', mot_de_passe: '', confirmation: '' }

const ROLES = [
  { valeur: 'client', titre: 'Je cherche un logement', texte: 'Consulter les annonces et contacter les propriétaires.' },
  { valeur: 'proprietaire', titre: 'Je propose des biens', texte: 'Publier et gérer mes annonces dans mon espace.' },
]

/** Page d'inscription : choix du type de compte, informations, mot de passe avec indicateur de force. */
export default function InscriptionPage() {
  const { utilisateur, inscrire } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const retour = cheminRetourSur(searchParams.get('retour'))
  const [valeurs, setValeurs] = useState(VALEURS_VIDES)
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)

  if (utilisateur && !envoiEnCours) return <Navigate to="/" replace />

  function modifier(event) {
    const { name, value } = event.target
    setValeurs((v) => ({ ...v, [name]: value }))
    setErreurs((e) => ({ ...e, [name]: undefined }))
  }

  async function soumettre(event) {
    event.preventDefault()
    setErreurGenerale(null)
    const erreursClient = validerInscription(valeurs)
    setErreurs(erreursClient)
    if (Object.keys(erreursClient).length > 0) {
      setErreurGenerale('Le formulaire contient des erreurs : corrigez les champs signalés.')
      return
    }

    const { confirmation: _confirmation, ...donnees } = valeurs
    for (const champ of ['telephone', 'ville']) if (!donnees[champ].trim()) delete donnees[champ]
    setEnvoiEnCours(true)
    try {
      const compte = await inscrire(donnees)
      const accueil = compte.role === 'proprietaire' ? '/espace' : '/'
      navigate(retour ?? accueil, { replace: true, state: { succes: `Bienvenue ${compte.prenom} ! Votre compte est créé.` } })
    } catch (error) {
      const { message, champs } = lireErreur(error)
      // 409 : email déjà utilisé → affiché sous le champ email.
      const parChamp = error?.response?.status === 409 ? { email: [message] } : champs
      setErreurs(parChamp)
      setErreurGenerale(error?.response?.status === 409 ? null : message)
      setEnvoiEnCours(false)
    }
  }

  return (
    <section className="page page--auth">
      <div className="carte-auth carte-auth--large">
        <h1>Créer un compte</h1>
        <p className="page__intro">Les champs marqués d'un * sont obligatoires.</p>
        <form className="formulaire" onSubmit={soumettre} noValidate aria-busy={envoiEnCours}>
          {erreurGenerale && (
            <p className="etat etat--erreur formulaire__alerte" role="alert">
              {erreurGenerale}
            </p>
          )}

          <fieldset
            className="choix-role"
            aria-invalid={erreurs.role ? 'true' : undefined}
            aria-describedby={erreurs.role ? 'erreur-role' : undefined}
          >
            <legend>Type de compte *</legend>
            <div className="choix-role__options">
              {ROLES.map((role) => (
                <label key={role.valeur} className="choix-role__option">
                  <input type="radio" name="role" value={role.valeur} checked={valeurs.role === role.valeur} onChange={modifier} />
                  <span className="choix-role__titre">{role.titre}</span>
                  <span className="choix-role__texte">{role.texte}</span>
                </label>
              ))}
            </div>
            {erreurs.role && (
              <p className="champ__erreur" id="erreur-role">
                {erreurs.role.join(' ')}
              </p>
            )}
          </fieldset>

          <div className="formulaire__grille formulaire__grille--nue">
            <Champ nom="prenom" libelle="Prénom *" erreurs={erreurs.prenom}>
              {(aria) => <input {...aria} type="text" autoComplete="given-name" value={valeurs.prenom} onChange={modifier} />}
            </Champ>
            <Champ nom="nom" libelle="Nom *" erreurs={erreurs.nom}>
              {(aria) => <input {...aria} type="text" autoComplete="family-name" value={valeurs.nom} onChange={modifier} />}
            </Champ>
          </div>
          <Champ nom="email" libelle="Email *" erreurs={erreurs.email}>
            {(aria) => <input {...aria} type="email" autoComplete="email" value={valeurs.email} onChange={modifier} />}
          </Champ>
          <div className="formulaire__grille formulaire__grille--nue">
            <Champ nom="telephone" libelle="Téléphone" erreurs={erreurs.telephone}>
              {(aria) => <input {...aria} type="tel" autoComplete="tel" value={valeurs.telephone} onChange={modifier} />}
            </Champ>
            <Champ nom="ville" libelle="Ville" erreurs={erreurs.ville}>
              {(aria) => <input {...aria} type="text" autoComplete="address-level2" value={valeurs.ville} onChange={modifier} />}
            </Champ>
          </div>
          <Champ nom="mot_de_passe" libelle="Mot de passe *" erreurs={erreurs.mot_de_passe}>
            {(aria) => (
              <ChampMotDePasse
                aria={{ ...aria, 'aria-describedby': [aria['aria-describedby'], 'force-mot-de-passe'].filter(Boolean).join(' ') }}
                value={valeurs.mot_de_passe}
                onChange={modifier}
                autoComplete="new-password"
              />
            )}
          </Champ>
          <ForceMotDePasse motDePasse={valeurs.mot_de_passe} id="force-mot-de-passe" />
          <Champ nom="confirmation" libelle="Confirmer le mot de passe *" erreurs={erreurs.confirmation}>
            {(aria) => (
              <ChampMotDePasse aria={aria} value={valeurs.confirmation} onChange={modifier} autoComplete="new-password" />
            )}
          </Champ>

          <button type="submit" className="bouton bouton--principal bouton--large" disabled={envoiEnCours}>
            {envoiEnCours ? 'Création du compte…' : 'Créer mon compte'}
          </button>
        </form>
        <p className="carte-auth__pied">
          Déjà inscrit ? <Link to={retour ? `/connexion?retour=${encodeURIComponent(retour)}` : '/connexion'}>Se connecter</Link>
        </p>
      </div>
    </section>
  )
}
