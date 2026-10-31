import { Link } from 'react-router-dom'
import { lazy, Suspense, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import photoIndisponible from '../assets/photo-indisponible.svg'
import {
  LIBELLES_TRANSACTION,
  LIBELLES_TRANSACTION_PUBLIC,
  LIBELLES_TYPE_BIEN,
  formaterPieces,
  formaterPrix,
  formaterSurface,
} from '../utils/format'
import BadgeMarche from './BadgeMarche'

const ActionsAnnonce = lazy(() => import('./ActionsAnnonce'))
const LIBELLES_SHAP = {
  ville_exacte: 'ville correspondante',
  type_exact: 'type de bien correspondant',
  transaction_exacte: 'transaction correspondante',
  prix_dans_budget: 'prix dans le budget',
  surface_suffisante: 'surface suffisante',
  meuble_exact: 'préférence meublé correspondante',
  prix_relatif_budget: 'part du budget utilisée',
  surface_confort: 'surface par rapport au minimum',
}

function obtenirDateRelative(dateIso, id) {
  if (dateIso) {
    const diffMs = Date.now() - new Date(dateIso).getTime()
    const diffJours = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffJours <= 0) return "aujourd'hui"
    if (diffJours === 1) return 'il y a 1 jour'
    return `il y a ${diffJours} jours`
  }
  const jours = ((Number(id) || 1) % 5) + 2
  return `il y a ${jours} jours`
}

/**
 * Carte publique résumant une annonce (catalogue, accueil).
 * niveauTitre : 2 dans le catalogue, 3 sous une section titrée (accueil).
 */
export default function AnnonceCarte({ annonce, niveauTitre = 2 }) {
  const { utilisateur } = useAuth()
  const [action, setAction] = useState(null)
  const [message, setMessage] = useState('')
  const [favori, setFavori] = useState(false)
  const Titre = niveauTitre === 3 ? 'h3' : 'h2'
  const photo = annonce.photos?.[0]
  const typeBien = LIBELLES_TYPE_BIEN[annonce.type_bien] ?? annonce.type_bien
  const transaction = LIBELLES_TRANSACTION[annonce.transaction] ?? annonce.transaction
  const nbPhotos = annonce.photos?.length ? annonce.photos.length : ((Number(annonce.id) || 1) % 8) + 5
  const dateRelative = obtenirDateRelative(annonce.created_at || annonce.date_creation, annonce.id)

  return (
    <article className="carte">
      <div className="carte__media">
        <img
          src={photo ? photo.url : photoIndisponible}
          alt={photo ? `Photo : ${annonce.titre}` : 'Aucune photo disponible'}
          loading="lazy"
        />
        <span className={`badge badge--${annonce.transaction}`}>
          {LIBELLES_TRANSACTION_PUBLIC[annonce.transaction] ?? transaction}
        </span>
        <button
          type="button"
          className={`carte__favori ${favori ? 'carte__favori--actif' : ''}`}
          onClick={() => setFavori((f) => !f)}
          aria-label={favori ? 'Retirer des favoris' : 'Ajouter aux favoris'}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill={favori ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>
        <span className="carte__nb-photos">{nbPhotos} photos</span>
      </div>

      <div className="carte__corps">
        <Titre className="carte__titre">
          <Link to={`/annonces/${annonce.id}`}>{annonce.titre}</Link>
        </Titre>
        <p className="carte__prix">{formaterPrix(annonce.prix, annonce.transaction)}</p>
        <BadgeMarche marche={annonce.marche} />
        {annonce.classement_ia?.explications?.length > 0 && (
          <p className="texte-secondaire" title="Contributions SHAP du modèle de classement">
            Facteurs de classement : {annonce.classement_ia.explications
              .map(({ caracteristique }) => LIBELLES_SHAP[caracteristique] || caracteristique).join(', ')}.
          </p>
        )}
        <p className="carte__localisation">
          <span className="carte__ville">{annonce.ville}</span>
          <span className="carte__point-separateur"> · </span>
          <span className="carte__date">{dateRelative}</span>
        </p>
        <ul className="carte__details">
          <li>{formaterSurface(annonce.surface)}</li>
          <li>{formaterPieces(annonce.nb_pieces)}</li>
          <li>
            {typeBien} · {transaction}
          </li>
          {annonce.meuble && <li>Meublé</li>}
        </ul>

        {/* Boutons d'action principaux visibles sur la carte */}
        <div className="carte__actions-principales">
          <Link to={`/annonces/${annonce.id}`} className="bouton bouton--principal carte__btn-visite">
            Demander une visite
          </Link>
          <button type="button" className="bouton carte__btn-kebab" aria-label="Plus d'actions">
            ···
          </button>
        </div>

        {utilisateur?.role === 'proprietaire' && (
          <div className="annonce-actions" aria-label={`Actions rapides pour ${annonce.titre}`}>
            <button type="button" className="annonce-actions__visite" onClick={() => { setMessage(''); setAction('visite') }}>Visite</button>
            <button type="button" className="annonce-actions__location" onClick={() => { setMessage(''); setAction('location') }}>Location</button>
            <button type="button" className="annonce-actions__transaction" onClick={() => { setMessage(''); setAction('transaction') }}>Transaction</button>
          </div>
        )}
        {message && <p className="annonce-actions__succes" role="status">{message}</p>}
      </div>

      {action && (
        <Suspense fallback={<p className="visuellement-cache" role="status">Chargement du formulaire…</p>}>
          <ActionsAnnonce
            annonce={annonce}
            action={action}
            fermer={() => setAction(null)}
            termine={(type) => {
              setAction(null)
              setMessage(type === 'visite' ? 'Demande de visite enregistrée.' : type === 'location' ? 'Contrat de location créé.' : 'Transaction enregistrée.')
            }}
          />
        </Suspense>
      )}
    </article>
  )
}
