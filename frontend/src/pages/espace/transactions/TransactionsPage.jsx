import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listerTransactions, supprimerTransaction } from '../../../api/transactions'
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

export default function TransactionsPage() {
  const [recherche, setRecherche] = useState('')
  const [statut, setStatut] = useState('')
  const [typeTrx, setTypeTrx] = useState('')
  const [transASupprimer, setTransASupprimer] = useState(null)
  const [suppressionEnCours, setSuppressionEnCours] = useState(false)

  const {
    donnees,
    etat,
    erreur,
    recharger,
  } = useRequete(['transactions', recherche, statut, typeTrx], () =>
    listerTransactions({ recherche, statut, type_transaction: typeTrx }),
  )

  const confirmerSuppression = async () => {
    if (!transASupprimer) return
    setSuppressionEnCours(true)
    try {
      await supprimerTransaction(transASupprimer.id)
      setTransASupprimer(null)
      recharger()
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors de la suppression')
    } finally {
      setSuppressionEnCours(false)
    }
  }

  const items = donnees?.items || []
  const enCoursCount = items.filter((t) => ['en_negociation', 'en_cours', 'payee_partiellement'].includes(t.statut)).length
  const reservationsCount = items.filter((t) => t.statut === 'reservee').length
  const finaliseesCount = items.filter((t) => t.statut === 'finalisee').length
  const encaisse = items.reduce((somme, t) => somme + Number(t.acompte || 0), 0)

  return (
    <section className="page espace-page espace-page--transactions">
      <div className="page__entete espace-page__entete">
        <div>
          <h1>Gestion des transactions</h1>
          <p className="texte-secondaire">Suivez les ventes, réservations et encaissements de vos biens en dinars tunisiens (TND).</p>
        </div>
        <Link to="/espace/transactions/nouvelle" className="bouton bouton--principal">
          + Nouvelle transaction
        </Link>
      </div>

      {etat === 'succes' && <div className="espace-page__stats">
        <article><span>En cours</span><strong>{enCoursCount}</strong></article>
        <article><span>Réservations</span><strong className="stat--orange">{reservationsCount}</strong></article>
        <article><span>Ventes conclues</span><strong className="stat--succes">{finaliseesCount}</strong></article>
        <article><span>Encaissé (TND)</span><strong>{encaisse.toLocaleString('fr-FR')}</strong></article>
      </div>}

      <div className="filtres-barre transactions__filtres">
        <input
          type="search"
          placeholder="Rechercher par référence, bien, acheteur, notaire…"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          className="champ-saisie filtres-barre__recherche"
        />
        <select
          value={statut}
          onChange={(e) => setStatut(e.target.value)}
          className="champ-saisie filtres-barre__select"
        >
          <option value="">Tous les statuts</option>
          <option value="en_negociation">En négociation</option>
          <option value="reservee">Réservée</option>
          <option value="en_cours">En cours</option>
          <option value="payee_partiellement">Partiellement payée</option>
          <option value="finalisee">Finalisée</option>
          <option value="annulee">Annulée</option>
        </select>
        <button type="button" className="bouton bouton--secondaire" onClick={() => { setRecherche(''); setStatut(''); setTypeTrx('') }} disabled={!recherche && !statut && !typeTrx}>Réinitialiser</button>
        <select
          value={typeTrx}
          onChange={(e) => setTypeTrx(e.target.value)}
          className="champ-saisie filtres-barre__select"
        >
          <option value="">Tous les types</option>
          <option value="vente">Vente</option>
          <option value="location">Location</option>
          <option value="reservation">Réservation</option>
        </select>
      </div>

      {etat === 'chargement' && <p className="etat">Chargement des transactions…</p>}
      {etat === 'erreur' && <p className="etat etat--erreur">{erreur?.message || 'Erreur de chargement.'}</p>}

      {etat === 'succes' && items.length === 0 && (
        <div className="panneau etat-vide espace-page__vide">
          <span className="espace-page__vide-icone" aria-hidden="true">🤝</span><h2>Aucune transaction pour le moment</h2><p>Enregistrez une vente, une réservation ou un encaissement pour suivre vos paiements en TND.</p>
          <Link to="/espace/transactions/nouvelle" className="bouton bouton--secondaire">
            Enregistrer une transaction
          </Link>
        </div>
      )}

      {etat === 'succes' && items.length > 0 && (
        <div className="table-conteneur">
          <table className="table-donnees">
            <thead>
              <tr>
                <th>Réf.</th>
                <th>Bien & Type</th>
                <th>Acheteur / Client</th>
                <th>Montant total</th>
                <th>Acompte versé</th>
                <th>Reste dû</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => {
                const b = BADGES_STATUT_TRX[t.statut] || { classe: 'badge--gris', libelle: t.statut }
                const pct = t.montant_total > 0 ? Math.round((t.acompte / t.montant_total) * 100) : 0
                return (
                  <tr key={t.id}>
                    <td>
                      <span className="reference-code">{t.reference}</span>
                    </td>
                    <td>
                      <strong>{t.titre_annonce}</strong>
                      <div>
                        <span className="etiquette-type">{t.type_transaction.toUpperCase()}</span>
                      </div>
                    </td>
                    <td>{t.acheteur_nom}</td>
                    <td>
                      <strong>{t.montant_total.toLocaleString('fr-FR')} TND</strong>
                    </td>
                    <td>
                      <span className="texte-succes">{t.acompte.toLocaleString('fr-FR')} TND</span>
                      <small className="texte-discret"> ({pct}%)</small>
                    </td>
                    <td>
                      <span className={t.reste_a_payer > 0 ? 'texte-alerte' : 'texte-succes'}>
                        {t.reste_a_payer.toLocaleString('fr-FR')} TND
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${b.classe}`}>{b.libelle}</span>
                    </td>
                    <td>
                      <div className="actions-cell">
                        <Link to={`/espace/transactions/${t.id}`} className="bouton-lien">
                          Détail
                        </Link>
                        <Link to={`/espace/transactions/${t.id}/modifier`} className="bouton-lien">
                          Modifier
                        </Link>
                        <button
                          type="button"
                          className="bouton-lien bouton-lien--danger"
                          onClick={() => setTransASupprimer(t)}
                        >
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <ModalConfirmation
        ouvert={!!transASupprimer}
        titre="Supprimer cette transaction"
        message={`Voulez-vous supprimer définitivement la transaction ${transASupprimer?.reference} d'un montant de ${transASupprimer?.montant_total} TND ?`}
        texteConfirmer="Supprimer"
        onConfirmer={confirmerSuppression}
        onAnnuler={() => setTransASupprimer(null)}
        chargement={suppressionEnCours}
      />
    </section>
  )
}
