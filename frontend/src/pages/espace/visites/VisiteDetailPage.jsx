import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { modifierVisite, obtenirVisite, supprimerVisite } from '../../../api/visites'
import ModalConfirmation from '../../../components/ModalConfirmation'
import { useRequete } from '../../../hooks/useRequete'

const BADGES_STATUT = {
  en_attente: { classe: 'badge--orange', libelle: 'En attente' },
  confirmee: { classe: 'badge--vert', libelle: 'Confirmée' },
  refusee: { classe: 'badge--rouge', libelle: 'Refusée' },
  annulee: { classe: 'badge--gris', libelle: 'Annulée' },
  reportee: { classe: 'badge--bleu', libelle: 'Reportée' },
  effectuee: { classe: 'badge--vert', libelle: 'Effectuée' },
  absent: { classe: 'badge--rouge', libelle: 'Absent' },
}

export default function VisiteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [modaleSuppression, setModaleSuppression] = useState(false)
  const [chargementAction, setChargementAction] = useState(false)

  const {
    donnees: v,
    etat,
    erreur,
    recharger,
  } = useRequete(['visite', id], () => obtenirVisite(id))

  const changerStatut = async (nouveauStatut) => {
    setChargementAction(true)
    try {
      await modifierVisite(id, { statut: nouveauStatut })
      recharger()
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors du changement de statut')
    } finally {
      setChargementAction(false)
    }
  }

  const handleSupprimer = async () => {
    setChargementAction(true)
    try {
      await supprimerVisite(id)
      navigate('/espace/visites')
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors de la suppression')
      setChargementAction(false)
    }
  }

  if (etat === 'chargement') return <p className="etat">Chargement de la visite…</p>
  if (etat === 'erreur' || !v) return <p className="etat etat--erreur">{erreur?.message || 'Visite introuvable.'}</p>

  const badge = BADGES_STATUT[v.statut] || { classe: 'badge--gris', libelle: v.statut }

  return (
    <section className="page">
      <div className="page__entete">
        <div>
          <div className="page__sur-titre">Visite immobilière — {v.reference}</div>
          <h1>{v.titre_annonce}</h1>
        </div>
        <div className="actions-groupe">
          <Link to={`/espace/visites/${id}/modifier`} className="bouton bouton--secondaire">
            Modifier
          </Link>
          <button
            type="button"
            className="bouton bouton--danger"
            onClick={() => setModaleSuppression(true)}
          >
            Supprimer
          </button>
        </div>
      </div>

      <div className="detail-grille">
        <div className="panneau">
          <h2>Informations sur le rendez-vous</h2>
          <dl className="liste-definition">
            <dt>Statut :</dt>
            <dd>
              <span className={`badge ${badge.classe}`}>{badge.libelle}</span>
            </dd>

            <dt>Date de la visite :</dt>
            <dd>
              <strong>{v.date_visite}</strong> de {v.heure_debut} à {v.heure_fin}
            </dd>

            <dt>Format :</dt>
            <dd>{v.type_visite === 'virtuelle' ? '📹 Visite virtuelle en ligne' : '📍 Visite sur place'}</dd>

            <dt>Nombre de personnes :</dt>
            <dd>{v.nb_personnes} visiteur(s)</dd>

            <dt>Téléphone de contact :</dt>
            <dd>
              <a href={`tel:${v.telephone_contact}`}>{v.telephone_contact}</a>
            </dd>

            <dt>Date de la demande :</dt>
            <dd>{v.date_demande ? new Date(v.date_demande).toLocaleString('fr-FR') : '—'}</dd>

            {v.date_confirmation && (
              <>
                <dt>Confirmée le :</dt>
                <dd>{new Date(v.date_confirmation).toLocaleString('fr-FR')}</dd>
              </>
            )}
          </dl>

          {v.message_client && (
            <div className="remarque-boite">
              <h4>Note / Message du visiteur :</h4>
              <p>{v.message_client}</p>
            </div>
          )}

          {v.feedback_client && (
            <div className="remarque-boite">
              <h4>Avis / Retour d'expérience :</h4>
              <p>{v.feedback_client}</p>
              {v.note_visite && <p>Note attribuée : {'★'.repeat(v.note_visite)}{'☆'.repeat(5 - v.note_visite)}</p>}
            </div>
          )}
        </div>

        <div className="panneau">
          <h2>Actions rapides de statut</h2>
          <p className="texte-secondaire">Faites évoluer l'état de cette visite selon vos échanges avec le visiteur.</p>

          <div className="boutons-verticaux">
            {v.statut === 'en_attente' && (
              <>
                <button
                  type="button"
                  className="bouton bouton--succes"
                  onClick={() => changerStatut('confirmee')}
                  disabled={chargementAction}
                >
                  ✅ Confirmer la visite
                </button>
                <button
                  type="button"
                  className="bouton bouton--danger"
                  onClick={() => changerStatut('refusee')}
                  disabled={chargementAction}
                >
                  ❌ Refuser la visite
                </button>
              </>
            )}

            {v.statut === 'confirmee' && (
              <>
                <button
                  type="button"
                  className="bouton bouton--principal"
                  onClick={() => changerStatut('effectuee')}
                  disabled={chargementAction}
                >
                  🎉 Marquer comme effectuée
                </button>
                <button
                  type="button"
                  className="bouton bouton--secondaire"
                  onClick={() => changerStatut('absent')}
                  disabled={chargementAction}
                >
                  ⚠️ Visiteur absent
                </button>
                <button
                  type="button"
                  className="bouton bouton--secondaire"
                  onClick={() => changerStatut('annulee')}
                  disabled={chargementAction}
                >
                  Annuler le rendez-vous
                </button>
              </>
            )}

            {(v.statut === 'refusee' || v.statut === 'annulee' || v.statut === 'effectuee') && (
              <button
                type="button"
                className="bouton bouton--secondaire"
                onClick={() => changerStatut('en_attente')}
                disabled={chargementAction}
              >
                Remettre en attente
              </button>
            )}
          </div>

          <hr className="separateur" />

          <h3>Interlocuteurs</h3>
          <p><strong>Visiteur :</strong> {v.client_nom} ({v.client_email || 'email non renseigné'})</p>
          <p><strong>Propriétaire :</strong> {v.proprietaire_nom}</p>
        </div>
      </div>

      <ModalConfirmation
        ouvert={modaleSuppression}
        titre="Supprimer cette visite"
        message={`Confirmez-vous la suppression de la visite ${v.reference} ?`}
        texteConfirmer="Supprimer"
        onConfirmer={handleSupprimer}
        onAnnuler={() => setModaleSuppression(false)}
        chargement={chargementAction}
      />
    </section>
  )
}
