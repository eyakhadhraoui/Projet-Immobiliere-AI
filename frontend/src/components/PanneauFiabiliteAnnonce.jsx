import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  changerStatut,
  demanderRevueFiabilite,
  lireErreur,
  obtenirFiabiliteAnnonce,
} from '../api/annonces'

const LIBELLES_NIVEAU = {
  aucun_signal: 'Aucun signal',
  a_surveiller: 'À surveiller',
  a_verifier: 'À vérifier',
}

function photosBloquantes(raisons = []) {
  return raisons.some((raison) => ['photos_communes', 'photo_deja_refusee'].includes(raison.signal))
}

/** Affiche le dernier contrôle de fiabilité et les actions autorisées au propriétaire. */
export default function PanneauFiabiliteAnnonce({ annonce, onAnnonceModifiee }) {
  const [etat, setEtat] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let actif = true
    Promise.resolve()
      .then(() => obtenirFiabiliteAnnonce(annonce.id))
      .then((resultat) => { if (actif) setEtat(resultat) })
      .catch((error) => { if (actif) setErreur(lireErreur(error).message) })
      .finally(() => { if (actif) setChargement(false) })
    return () => { actif = false }
  }, [annonce.id])

  async function chargerEtat() {
    const resultat = await obtenirFiabiliteAnnonce(annonce.id)
    setEtat(resultat)
    return resultat
  }

  async function verifierEtPublier(confirmation = false) {
    setEnCours(true)
    setErreur('')
    setMessage('')
    try {
      const miseAJour = await changerStatut(annonce.id, 'publiee', confirmation)
      onAnnonceModifiee(miseAJour)
      if (miseAJour.fiabilite) {
        setEtat((precedent) => ({ ...precedent, controle: miseAJour.fiabilite, motif_attente: miseAJour.motif_attente }))
      }
      setMessage(miseAJour.statut === 'en_attente'
        ? 'Votre annonce est en attente de vérification. Ce contrôle automatique peut se tromper.'
        : 'Votre annonce est publiée. Ce contrôle automatique peut se tromper.')
    } catch (error) {
      const details = error.response?.data
      if (error.response?.status === 409 && details?.error === 'confirmation_requise') {
        setEtat((precedent) => ({ ...precedent, controle: details.fiabilite }))
      } else {
        if (details?.error === 'photos_deja_utilisees') {
          await chargerEtat()
        }
        setErreur(lireErreur(error).message)
      }
    } finally {
      setEnCours(false)
    }
  }

  async function demanderRevue() {
    setEnCours(true)
    setErreur('')
    try {
      const resultat = await demanderRevueFiabilite(annonce.id)
      setEtat((precedent) => ({ ...precedent, revue_demandee_le: resultat.revue_demandee_le }))
      setMessage('Votre demande de revue a été envoyée.')
    } catch (error) {
      setErreur(lireErreur(error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (chargement) return <p className="actions-annonce__aide" role="status">Chargement du contrôle de fiabilité…</p>
  if (erreur && !etat?.controle) {
    return <p className="champ__erreur" role="alert">État du contrôle indisponible : {erreur}</p>
  }

  const controle = etat?.controle
  const raisons = controle?.raisons || []
  const bloqueParPhoto = photosBloquantes(raisons)
  const enAttente = annonce.statut === 'en_attente' && etat?.motif_attente === 'fiabilite'
  const niveau = controle?.niveau || (enAttente ? 'attente' : 'inconnu')
  const libelle = LIBELLES_NIVEAU[niveau] || (enAttente ? 'En attente de vérification' : 'Pas encore contrôlée')
  const peutConfirmer = annonce.statut === 'brouillon' && niveau === 'a_surveiller' && !bloqueParPhoto

  return (
    <section className={`fiche__fiabilite fiche__fiabilite--${niveau}`} aria-labelledby="fiche-fiabilite-titre">
      <div className="fiche__fiabilite-entete">
        <h2 id="fiche-fiabilite-titre">Vérification automatique</h2>
        <span className={`fiabilite-badge fiabilite-badge--${niveau}`}>{libelle}</span>
      </div>

      {!controle && !enAttente && (
        <p>Le contrôle sera effectué lors de la publication de votre annonce.</p>
      )}

      {controle && niveau === 'aucun_signal' && (
        <p>Aucun signal n’a été relevé. Ce contrôle automatique peut se tromper.</p>
      )}

      {(niveau === 'a_surveiller' || niveau === 'a_verifier' || bloqueParPhoto) && (
        <>
          <h3>{enAttente ? 'Annonce en attente de vérification' : 'Avant de publier votre annonce'}</h3>
          {raisons.length > 0 ? (
            <ul className="fiabilite__raisons">
              {raisons.map((raison, index) => (
                <li key={`${raison.signal}-${index}`}>{raison.texte}</li>
              ))}
            </ul>
          ) : <p>Certains éléments de l’annonce demandent une vérification.</p>}
          {(controle?.annonces_liees || []).map((lien, index) => (
            lien.url ? (
              <p key={`${lien.annonce_id}-${index}`}>
                Annonce publique concernée : <Link to={lien.url}>{lien.titre}</Link>
              </p>
            ) : null
          ))}
          <p>Ce contrôle automatique peut se tromper.</p>
        </>
      )}

      {erreur && <p className="champ__erreur" role="alert">{erreur}</p>}
      {message && <p className="message-succes" role="status">{message}</p>}

      <div className="fiche__fiabilite-actions">
        {annonce.statut === 'brouillon' && !controle && (
          <button type="button" className="bouton bouton--principal" onClick={() => verifierEtPublier()} disabled={enCours}>
            {enCours ? 'Vérification…' : 'Vérifier et publier'}
          </button>
        )}
        {peutConfirmer && (
          <button type="button" className="bouton bouton--principal" onClick={() => verifierEtPublier(true)} disabled={enCours}>
            {enCours ? 'Vérification…' : 'Publier quand même'}
          </button>
        )}
        {bloqueParPhoto && annonce.statut !== 'publiee' && (
          <Link to={`/espace/annonces/${annonce.id}/modifier`} className="bouton bouton--principal">
            Remplacer ces photos
          </Link>
        )}
        {enAttente && !etat?.revue_demandee_le && (
          <button type="button" className="bouton" onClick={demanderRevue} disabled={enCours}>
            {enCours ? 'Envoi…' : 'Faire une réclamation'}
          </button>
        )}
        {etat?.revue_demandee_le && <p>Réclamation envoyée le {new Date(etat.revue_demandee_le).toLocaleDateString('fr-FR')}.</p>}
      </div>
    </section>
  )
}
