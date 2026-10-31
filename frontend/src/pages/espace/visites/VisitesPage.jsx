import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listerVisites, supprimerVisite } from '../../../api/visites'
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

export default function VisitesPage() {
  const [recherche, setRecherche] = useState('')
  const [statut, setStatut] = useState('')
  const [typeVisite, setTypeVisite] = useState('')
  const [visiteASupprimer, setVisiteASupprimer] = useState(null)
  const [suppressionEnCours, setSuppressionEnCours] = useState(false)

  const {
    donnees,
    etat,
    erreur,
    recharger,
  } = useRequete(['visites', recherche, statut, typeVisite], () =>
    listerVisites({ recherche, statut, type_visite: typeVisite }),
  )

  const confirmerSuppression = async () => {
    if (!visiteASupprimer) return
    setSuppressionEnCours(true)
    try {
      await supprimerVisite(visiteASupprimer.id)
      setVisiteASupprimer(null)
      recharger()
    } catch (err) {
      alert(err.response?.data?.message || 'Erreur lors de la suppression')
    } finally {
      setSuppressionEnCours(false)
    }
  }

  const items = donnees?.items || []
  const compteStatut = (valeur) => items.filter((visite) => visite.statut === valeur).length
  const reinitialiserFiltres = () => { setRecherche(''); setStatut(''); setTypeVisite('') }

  return (
    <section className="page visites-page espace-page espace-page--visites">
      <div className="page__entete espace-page__entete">
        <div>
          <h1>Gestion des visites</h1>
          <p className="texte-secondaire">Suivez les rendez-vous de visite programmés sur vos biens immobiliers.</p>
        </div>
        <Link to="/espace/visites/nouvelle" className="bouton bouton--principal">
          + Planifier une visite
        </Link>
      </div>

      {etat === 'succes' && <div className="visites__indicateurs" aria-label="Résumé des visites affichées">
        <article className="visites__indicateur"><span>En attente</span><strong className="visites__indicateur--attente">{compteStatut('en_attente')}</strong></article>
        <article className="visites__indicateur"><span>Confirmées</span><strong className="visites__indicateur--confirmee">{compteStatut('confirmee')}</strong></article>
        <article className="visites__indicateur"><span>Effectuées</span><strong className="visites__indicateur--effectuee">{compteStatut('effectuee')}</strong></article>
        <article className="visites__indicateur"><span>Absences</span><strong className="visites__indicateur--absent">{compteStatut('absent')}</strong></article>
      </div>}

      <div className="filtres-barre visites__filtres">
        <input
          type="search"
          placeholder="Rechercher par référence, bien, visiteur…"
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
          <option value="en_attente">En attente</option>
          <option value="confirmee">Confirmée</option>
          <option value="refusee">Refusée</option>
          <option value="annulee">Annulée</option>
          <option value="effectuee">Effectuée</option>
          <option value="absent">Absent</option>
        </select>
        <select
          value={typeVisite}
          onChange={(e) => setTypeVisite(e.target.value)}
          className="champ-saisie filtres-barre__select"
        >
          <option value="">Tous les types</option>
          <option value="sur_place">Sur place</option>
          <option value="virtuelle">Visite virtuelle</option>
        </select>
        <button type="button" className="bouton bouton--secondaire visites__reinitialiser" onClick={reinitialiserFiltres} disabled={!recherche && !statut && !typeVisite}>
          Réinitialiser
        </button>
      </div>

      {etat === 'chargement' && <p className="etat">Chargement des visites…</p>}
      {etat === 'erreur' && <p className="etat etat--erreur">{erreur?.message || 'Erreur de chargement.'}</p>}

      {etat === 'succes' && items.length === 0 && (
        <div className="panneau etat-vide">
          <p>Aucune visite ne correspond à vos critères.</p>
          <Link to="/espace/visites/nouvelle" className="bouton bouton--secondaire">
            Planifier la première visite
          </Link>
        </div>
      )}

      {etat === 'succes' && items.length > 0 && (
        <div className="table-conteneur">
          <table className="table-donnees visites__table">
            <thead>
              <tr>
                <th>Réf.</th>
                <th>Bien immobilier</th>
                <th>Visiteur</th>
                <th>Date & Heure</th>
                <th>Type</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((v) => {
                const b = BADGES_STATUT[v.statut] || { classe: 'badge--gris', libelle: v.statut }
                return (
                  <tr key={v.id}>
                    <td data-label="Référence">
                      <span className="reference-code">{v.reference}</span>
                    </td>
                    <td data-label="Bien immobilier">
                      <strong>{v.titre_annonce}</strong>
                      <span className="texte-discret"> ({v.ville_annonce})</span>
                    </td>
                    <td data-label="Visiteur">
                      <div>{v.client_nom}</div>
                      <small className="texte-discret">{v.telephone_contact}</small>
                    </td>
                    <td data-label="Date et heure">
                      <div>{v.date_visite}</div>
                      <small className="texte-discret">
                        {v.heure_debut} - {v.heure_fin}
                      </small>
                    </td>
                    <td data-label="Type">
                      <span className="etiquette-type">
                        {v.type_visite === 'virtuelle' ? '📹 Virtuelle' : '📍 Sur place'}
                      </span>
                    </td>
                    <td data-label="Statut">
                      <span className={`badge ${b.classe}`}>{b.libelle}</span>
                    </td>
                    <td data-label="Actions">
                      <div className="actions-cell">
                        <Link to={`/espace/visites/${v.id}`} className="bouton-lien" title="Consulter la visite">
                          Détail
                        </Link>
                        <Link to={`/espace/visites/${v.id}/modifier`} className="bouton-lien" title="Modifier">
                          Modifier
                        </Link>
                        <button
                          type="button"
                          className="bouton-lien bouton-lien--danger"
                          onClick={() => setVisiteASupprimer(v)}
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
        ouvert={!!visiteASupprimer}
        titre="Supprimer cette visite"
        message={`Êtes-vous sûr de vouloir supprimer définitivement la visite ${visiteASupprimer?.reference} pour « ${visiteASupprimer?.titre_annonce} » ? Cette action est irréversible.`}
        texteConfirmer="Supprimer la visite"
        onConfirmer={confirmerSuppression}
        onAnnuler={() => setVisiteASupprimer(null)}
        chargement={suppressionEnCours}
      />
    </section>
  )
}
