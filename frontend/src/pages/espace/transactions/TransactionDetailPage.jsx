import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ajouterPaiementTransaction,
  modifierTransaction,
  obtenirTransaction,
  supprimerTransaction,
} from '../../../api/transactions'
import ModalConfirmation from '../../../components/ModalConfirmation'
import { useRequete } from '../../../hooks/useRequete'

const BADGES_STATUT_TRX = {
  en_negociation: { classe: 'badge--gris', libelle: 'En négociation' },
  reservee: { classe: 'badge--bleu', libelle: 'Réservée' },
  en_cours: { classe: 'badge--orange', libelle: 'En cours' },
  payee_partiellement: { classe: 'badge--orange', libelle: 'Partiellement payée' },
  finalisee: { classe: 'badge--vert', libelle: 'Finalisée' },
  annulee: { classe: 'badge--rouge', libelle: 'Annulée' },
  litige: { classe: 'badge--rouge', libelle: 'En litige' },
}

export default function TransactionDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [modaleSuppression, setModaleSuppression] = useState(false)
  const [modalePaiement, setModalePaiement] = useState(false)
  const [chargementAction, setChargementAction] = useState(false)

  const [nouveauPaiement, setNouveauPaiement] = useState({
    montant: '',
    mode_paiement: 'virement',
    justificatif: '',
  })

  const {
    donnees: t,
    etat,
    erreur,
    recharger,
  } = useRequete(['transaction', id], () => obtenirTransaction(id))

  const handleAjouterPaiement = async (e) => {
    e.preventDefault()
    setChargementAction(true)
    try {
      await ajouterPaiementTransaction(id, nouveauPaiement)
      setModalePaiement(false)
      setNouveauPaiement({ montant: '', mode_paiement: 'virement', justificatif: '' })
      recharger()
    } catch (err) {
      alert(err.response?.data?.message || "Erreur lors de l'enregistrement du versement")
    } finally {
      setChargementAction(false)
    }
  }

  const handleChangerStatut = async (nouveauStatut) => {
    setChargementAction(true)
    try {
      await modifierTransaction(id, { statut: nouveauStatut })
      recharger()
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors de la mise à jour')
    } finally {
      setChargementAction(false)
    }
  }

  const handleSupprimer = async () => {
    setChargementAction(true)
    try {
      await supprimerTransaction(id)
      navigate('/espace/transactions')
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors de la suppression')
      setChargementAction(false)
    }
  }

  if (etat === 'chargement') return <p className="etat">Chargement de la transaction…</p>
  if (etat === 'erreur' || !t) return <p className="etat etat--erreur">{erreur?.message || 'Transaction introuvable.'}</p>

  const badge = BADGES_STATUT_TRX[t.statut] || { classe: 'badge--gris', libelle: t.statut }
  const pct = t.montant_total > 0 ? Math.min(100, Math.round((t.acompte / t.montant_total) * 100)) : 0

  return (
    <section className="page">
      <div className="page__entete">
        <div>
          <div className="page__sur-titre">Transaction immobilière — {t.reference}</div>
          <h1>{t.titre_annonce}</h1>
        </div>
        <div className="actions-groupe">
          <Link to={`/espace/transactions/${id}/modifier`} className="bouton bouton--secondaire">
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

      <div className="panneau recap-financier">
        <div className="chiffres">
          <div className="carte-chiffre">
            <span className="carte-chiffre__libelle">Montant total</span>
            <span className="carte-chiffre__valeur">{t.montant_total.toLocaleString('fr-FR')} TND</span>
          </div>
          <div className="carte-chiffre">
            <span className="carte-chiffre__libelle">Acompte / Payé</span>
            <span className="carte-chiffre__valeur texte-succes">{t.acompte.toLocaleString('fr-FR')} TND</span>
          </div>
          <div className="carte-chiffre">
            <span className="carte-chiffre__libelle">Solde restant dû</span>
            <span className={`carte-chiffre__valeur ${t.reste_a_payer > 0 ? 'texte-alerte' : 'texte-succes'}`}>
              {t.reste_a_payer.toLocaleString('fr-FR')} TND
            </span>
          </div>
          <div className="carte-chiffre">
            <span className="carte-chiffre__libelle">Statut actuel</span>
            <span className={`badge ${badge.classe}`}>{badge.libelle}</span>
          </div>
        </div>

        <div className="progression-barre-conteneur">
          <div className="progression-libelle">
            <span>Règlement de la transaction : {pct}% encaissés</span>
            <span>{t.acompte.toLocaleString('fr-FR')} / {t.montant_total.toLocaleString('fr-FR')} TND</span>
          </div>
          <div className="progression-barre">
            <div className="progression-remplie" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      <div className="detail-grille">
        <div className="panneau">
          <h2>Détails contractuels et juridiques</h2>
          <dl className="liste-definition">
            <dt>Type de contrat :</dt>
            <dd><span className="etiquette-type">{t.type_transaction.toUpperCase()}</span></dd>

            <dt>Acheteur / Preneur :</dt>
            <dd><strong>{t.acheteur_nom}</strong></dd>

            <dt>Vendeur / Propriétaire :</dt>
            <dd>{t.vendeur_nom}</dd>

            <dt>Mode de règlement :</dt>
            <dd>{t.mode_paiement.toUpperCase()}</dd>

            <dt>Notaire / Rédacteur :</dt>
            <dd>{t.notaire || 'Non spécifié'}</dd>

            <dt>N° de l'acte foncier :</dt>
            <dd>{t.reference_acte || 'En cours de rédaction'}</dd>

            <dt>Date de signature :</dt>
            <dd>{t.date_signature || 'À convenir'}</dd>

            <dt>Créée le :</dt>
            <dd>{t.date_transaction ? new Date(t.date_transaction).toLocaleString('fr-FR') : '—'}</dd>
          </dl>

          {t.observations && (
            <div className="remarque-boite">
              <h4>Observations et conditions :</h4>
              <p>{t.observations}</p>
            </div>
          )}
        </div>

        <div className="panneau">
          <div className="section__entete">
            <h2>Échéancier & Versements reçus</h2>
            {t.reste_a_payer > 0 && (
              <button
                type="button"
                className="bouton bouton--principal"
                onClick={() => setModalePaiement(true)}
              >
                + Enregistrer un versement
              </button>
            )}
          </div>

          {t.paiements.length === 0 ? (
            <p className="texte-secondaire">Aucun versement n'a encore été enregistré.</p>
          ) : (
            <ul className="paiements-liste">
              {t.paiements.map((p) => (
                <li key={p.id} className="paiement-item">
                  <div>
                    <strong>{p.montant.toLocaleString('fr-FR')} TND</strong>
                    <div className="texte-discret">
                      Réf: {p.reference_paiement} — {p.mode_paiement}
                    </div>
                  </div>
                  <div className="texte-droite">
                    <span className="badge badge--vert">Reçu</span>
                    <small className="texte-discret block">{new Date(p.date_paiement).toLocaleDateString('fr-FR')}</small>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <hr className="separateur" />

          <h3>Mise à jour rapide du statut</h3>
          <div className="boutons-verticaux">
            {t.statut !== 'finalisee' && (
              <button
                type="button"
                className="bouton bouton--succes"
                onClick={() => handleChangerStatut('finalisee')}
                disabled={chargementAction}
              >
                🏁 Marquer comme finalisée
              </button>
            )}
            {t.statut !== 'annulee' && (
              <button
                type="button"
                className="bouton bouton--secondaire"
                onClick={() => handleChangerStatut('annulee')}
                disabled={chargementAction}
              >
                Annuler la transaction
              </button>
            )}
          </div>
        </div>
      </div>

      {modalePaiement && (
        <div className="modale-overlay" role="dialog" aria-modal="true">
          <div className="modale-boite">
            <h3>Enregistrer un versement (Acompte / Tranche)</h3>
            <form onSubmit={handleAjouterPaiement}>
              <div className="form-groupe">
                <label>Montant reçu (TND) *</label>
                <input
                  type="number"
                  step="0.001"
                  required
                  placeholder={`Max conseillé : ${t.reste_a_payer} TND`}
                  value={nouveauPaiement.montant}
                  onChange={(e) => setNouveauPaiement({ ...nouveauPaiement, montant: e.target.value })}
                  className="champ-saisie"
                />
              </div>
              <div className="form-groupe">
                <label>Mode de paiement</label>
                <select
                  value={nouveauPaiement.mode_paiement}
                  onChange={(e) => setNouveauPaiement({ ...nouveauPaiement, mode_paiement: e.target.value })}
                  className="champ-saisie"
                >
                  <option value="virement">Virement bancaire</option>
                  <option value="cheque">Chèque certifié</option>
                  <option value="especes">Espèces</option>
                  <option value="carte">Carte</option>
                  <option value="flouci">Flouci</option>
                </select>
              </div>
              <div className="modale-actions">
                <button
                  type="button"
                  className="bouton bouton--secondaire"
                  onClick={() => setModalePaiement(false)}
                >
                  Annuler
                </button>
                <button type="submit" disabled={chargementAction} className="bouton bouton--principal">
                  {chargementAction ? 'Enregistrement…' : 'Valider le paiement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ModalConfirmation
        ouvert={modaleSuppression}
        titre="Supprimer cette transaction"
        message={`Confirmez-vous la suppression définitive de la transaction ${t.reference} ?`}
        texteConfirmer="Supprimer"
        onConfirmer={handleSupprimer}
        onAnnuler={() => setModaleSuppression(false)}
        chargement={chargementAction}
      />
    </section>
  )
}
