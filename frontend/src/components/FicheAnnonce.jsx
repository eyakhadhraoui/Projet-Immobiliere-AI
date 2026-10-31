import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { lireErreur, supprimerAnnonce } from '../api/annonces'
import { CARACTERISTIQUES } from '../utils/annonceForm'
import {
  LIBELLES_TRANSACTION,
  LIBELLES_TRANSACTION_PUBLIC,
  LIBELLES_TYPE_BIEN,
  formaterDate,
  formaterPieces,
  formaterPrix,
  formaterSurface,
} from '../utils/format'
import Avatar from './Avatar'
import BadgeMarche from './BadgeMarche'
import BadgeStatut from './BadgeStatut'
import ChangementStatut from './ChangementStatut'
import FenetreConfirmation from './FenetreConfirmation'
import FriseHistorique from './FriseHistorique'
import Galerie from './Galerie'
import PanneauFiabiliteAnnonce from './PanneauFiabiliteAnnonce'

/**
 * Détail complet d'une annonce.
 * - espace=false (site public) : informations seules ;
 * - espace=true (espace propriétaire) : statut, modification, suppression et frise d'historique.
 */
export default function FicheAnnonce({ annonce, onAnnonceModifiee, espace = false }) {
  const navigate = useNavigate()
  const [confirmationOuverte, setConfirmationOuverte] = useState(false)
  const [suppressionEnCours, setSuppressionEnCours] = useState(false)
  const [erreurSuppression, setErreurSuppression] = useState(null)

  const photos = annonce.photos ?? []
  const aCoordonnees = annonce.latitude !== null && annonce.latitude !== undefined
    && annonce.longitude !== null && annonce.longitude !== undefined

  async function supprimer() {
    setSuppressionEnCours(true)
    setErreurSuppression(null)
    try {
      await supprimerAnnonce(annonce.id)
      navigate('/espace/annonces', { state: { succes: `L'annonce « ${annonce.titre} » a été supprimée.` } })
    } catch (error) {
      setErreurSuppression(lireErreur(error).message)
      setSuppressionEnCours(false)
    }
  }

  function fermerConfirmation() {
    setConfirmationOuverte(false)
    setErreurSuppression(null)
  }

  return (
    <article className="fiche">
      <Link to={espace ? '/espace/annonces' : '/annonces'} className="fiche__retour">
        {espace ? '← Retour à mes annonces' : '← Retour aux annonces'}
      </Link>

      <div className="fiche__entete">
        <h1>{annonce.titre}</h1>
        {espace ? (
          <BadgeStatut statut={annonce.statut} />
        ) : (
          <span className={`badge badge--${annonce.transaction}`}>
            {LIBELLES_TRANSACTION_PUBLIC[annonce.transaction] ?? annonce.transaction}
          </span>
        )}
      </div>

      <div className="fiche__colonnes">
        {/* key : revient à la première photo si la liste change */}
        <Galerie key={photos.map((p) => p.id).join('-')} photos={photos} titre={annonce.titre} />

        <div className="fiche__infos">
          <p className="fiche__prix">{formaterPrix(annonce.prix, annonce.transaction)}</p>
          {/* Badge réservé au site public (dans l'espace propriétaire, l'API ne le calcule pas). */}
          {!espace && <BadgeMarche marche={annonce.marche} />}
          <p className="fiche__adresse">
            {annonce.adresse}, {annonce.ville}
          </p>

          <dl className="fiche__liste">
            <dt>Type de bien</dt>
            <dd>{LIBELLES_TYPE_BIEN[annonce.type_bien] ?? annonce.type_bien}</dd>
            <dt>Transaction</dt>
            <dd>{LIBELLES_TRANSACTION[annonce.transaction] ?? annonce.transaction}</dd>
            <dt>Surface</dt>
            <dd>{formaterSurface(annonce.surface)}</dd>
            <dt>Pièces</dt>
            <dd>{formaterPieces(annonce.nb_pieces)}</dd>
            <dt>Meublé</dt>
            <dd>{annonce.meuble ? 'Oui' : 'Non'}</dd>
            {aCoordonnees && (
              <>
                <dt>Coordonnées</dt>
                <dd>
                  {annonce.latitude}, {annonce.longitude}
                </dd>
              </>
            )}
            {espace && annonce.created_at && (
              <>
                <dt>Créée le</dt>
                <dd>{formaterDate(annonce.created_at)}</dd>
              </>
            )}
            {annonce.updated_at && (
              <>
                <dt>{espace ? 'Modifiée le' : 'Mise à jour le'}</dt>
                <dd>{formaterDate(annonce.updated_at)}</dd>
              </>
            )}
          </dl>

          {!espace && annonce.proprietaire && (
            <div className="fiche__proprietaire">
              <Avatar utilisateur={annonce.proprietaire} taille="moyen" />
              <p>
                Proposé par <strong>{annonce.proprietaire.prenom}</strong>
              </p>
            </div>
          )}

          {espace && (
            <>
              <ChangementStatut annonce={annonce} onStatutChange={onAnnonceModifiee} />
              <PanneauFiabiliteAnnonce annonce={annonce} onAnnonceModifiee={onAnnonceModifiee} />

              <div className="fiche__actions">
                <Link to={`/espace/annonces/${annonce.id}/modifier`} className="bouton bouton--principal">
                  Modifier
                </Link>
                <button type="button" className="bouton bouton--danger" onClick={() => setConfirmationOuverte(true)}>
                  Supprimer
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <section className="fiche__section">
        <h2>Description</h2>
        <p className="fiche__description">{annonce.description}</p>
      </section>

      <section className="fiche__section">
        <h2>Caractéristiques</h2>
        {annonce.caracteristiques?.length > 0 ? (
          <ul className="carte__details">
            {annonce.caracteristiques.map((c) => (
              <li key={c}>{CARACTERISTIQUES[c] ?? c}</li>
            ))}
          </ul>
        ) : (
          <p>Aucune caractéristique renseignée.</p>
        )}
      </section>

      {/* key : recharge la frise après un changement de statut (updated_at change) */}
      {espace && <FriseHistorique key={`${annonce.id}-${annonce.updated_at}`} annonceId={annonce.id} />}

      {confirmationOuverte && (
        <FenetreConfirmation
          titre="Supprimer cette annonce ?"
          message={`L'annonce « ${annonce.titre} » et ses photos seront définitivement supprimées.`}
          libelleConfirmer="Supprimer définitivement"
          libelleEnCours="Suppression…"
          enCours={suppressionEnCours}
          erreur={erreurSuppression}
          onConfirmer={supprimer}
          onAnnuler={fermerConfirmation}
        />
      )}
    </article>
  )
}
