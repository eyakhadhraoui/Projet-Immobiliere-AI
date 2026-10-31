import { Link } from 'react-router-dom'
import { obtenirStatistiques } from '../../api/historique'
import CarteChiffre from '../../components/CarteChiffre'
import EntreeHistorique from '../../components/EntreeHistorique'
import MessageErreur from '../../components/MessageErreur'
import Repartition from '../../components/Repartition'
import { useRequete } from '../../hooks/useRequete'
import { LIBELLES_STATUT, LIBELLES_TYPE_BIEN, formaterNombre, formaterPrix } from '../../utils/format'

const enValeurs = (comptes, libelles) =>
  Object.entries(libelles).map(([cle, libelle]) => ({ cle, libelle, nombre: comptes?.[cle] ?? 0 }))

const prixOuTiret = (prix, transaction) => (prix == null ? '—' : formaterPrix(prix, transaction))

const dateCourte = (dateIso) => {
  if (!dateIso) return 'Date à confirmer'
  const [annee, mois, jour] = dateIso.split('-')
  return annee && mois && jour ? `${jour}/${mois}` : dateIso
}

const LIBELLES_VISITE = {
  en_attente: 'En attente',
  confirmee: 'Confirmée',
  refusee: 'Refusée',
  annulee: 'Annulée',
  reportee: 'Reportée',
  effectuee: 'Effectuée',
  absent: 'Absent',
}

const CLASSES_VISITE = {
  en_attente: 'tableau__statut--attente',
  confirmee: 'tableau__statut--succes',
  refusee: 'tableau__statut--erreur',
  annulee: 'tableau__statut--neutre',
  reportee: 'tableau__statut--info',
  effectuee: 'tableau__statut--succes',
  absent: 'tableau__statut--erreur',
}

const LIBELLES_LOYER = {
  a_payer: 'À payer',
  paye: 'Payé',
  partiel: 'Partiel',
  en_retard: 'En retard',
}

const CLASSES_LOYER = {
  a_payer: 'tableau__statut--info',
  paye: 'tableau__statut--succes',
  partiel: 'tableau__statut--attente',
  en_retard: 'tableau__statut--erreur',
}

const JOURS_SEMAINE = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const HEURES_JOUR = Array.from({ length: 24 }, (_, heure) => heure)

function CarteChaleurAbsences({ donnees = [] }) {
  const cases = new Map(donnees.map((item) => [`${item.jour}-${item.heure}`, item]))
  const classeTaux = (taux) => taux >= 0.5 ? 'eleve' : taux >= 0.2 ? 'moyen' : 'faible'

  return (
    <section className="panneau tableau__carte-absence" aria-labelledby="titre-carte-absence">
      <div className="section__entete">
        <div>
          <h2 id="titre-carte-absence">Taux d'absence par jour et heure</h2>
          <p>Visites terminées de vos annonces. Une case vide indique qu'aucune visite n'a eu lieu sur ce créneau.</p>
        </div>
      </div>
      <div className="tableau__carte-absence-defilement">
        <div className="tableau__carte-absence-grille" role="table" aria-label="Taux d'absence par jour de la semaine et heure">
          <div className="tableau__absence-ligne" role="row">
            <span className="tableau__absence-entete" role="columnheader">Jour / heure</span>
            {HEURES_JOUR.map((heure) => <span className="tableau__absence-entete" role="columnheader" key={heure}>{String(heure).padStart(2, '0')}</span>)}
          </div>
          {JOURS_SEMAINE.map((jour, indexJour) => (
            <div className="tableau__absence-ligne" role="row" key={jour}>
              <strong className="tableau__absence-jour" role="rowheader">{jour}</strong>
              {HEURES_JOUR.map((heure) => {
                const item = cases.get(`${indexJour}-${heure}`)
                const taux = item?.taux ?? 0
                const texte = item ? `${Math.round(taux * 100)}%` : '·'
                const libelle = item
                  ? `${jour} ${String(heure).padStart(2, '0')} h : ${texte} d'absence sur ${item.total} visite${item.total > 1 ? 's' : ''}`
                  : `${jour} ${String(heure).padStart(2, '0')} h : aucune visite terminée`
                return <span
                  key={heure}
                  role="cell"
                  className={`tableau__absence-case${item ? ` tableau__absence-case--${classeTaux(taux)}` : ' tableau__absence-case--vide'}`}
                  aria-label={libelle}
                  title={libelle}
                >{texte}</span>
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="tableau__absence-legende" aria-label="Légende du taux d'absence">
        <span><i className="tableau__absence-case--faible" />Moins de 20 %</span>
        <span><i className="tableau__absence-case--moyen" />De 20 à 49 %</span>
        <span><i className="tableau__absence-case--eleve" />50 % et plus</span>
      </div>
    </section>
  )
}

function ListeVisites({ visites = [] }) {
  return (
    <section className="panneau tableau__action-carte" aria-labelledby="titre-prochaines-visites">
      <div className="section__entete">
        <h2 id="titre-prochaines-visites">Prochaines visites</h2>
      </div>
      {visites.length === 0 ? (
        <div className="tableau__action-corps">
          <p className="tableau__action-texte">Aucune visite programmée.</p>
          <Link to="/annonces" className="tableau__action-lien">
            Partager une annonce pour recevoir des visites →
          </Link>
        </div>
      ) : (
        <div className="tableau__action-corps">
          <ul className="tableau__lignes">
            {visites.slice(0, 3).map((visite) => (
              <li key={visite.id}>
                <Link className="tableau__ligne" to={`/espace/visites/${visite.id}`}>
                  <span className="tableau__nom">{visite.titre_annonce || 'Annonce immobilière'}</span>
                  <span className="tableau__date">
                    {dateCourte(visite.date_visite)} · {visite.heure_debut || '—'}
                  </span>
                  <span className={`tableau__statut ${CLASSES_VISITE[visite.statut] || ''}`}>
                    {LIBELLES_VISITE[visite.statut] || visite.statut}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Link to="/espace/visites" className="tableau__action-lien">
            Voir les visites →
          </Link>
        </div>
      )}
    </section>
  )
}

function ListeLoyers({ loyers = [] }) {
  return (
    <section className="panneau tableau__action-carte" aria-labelledby="titre-loyers-a-encaisser">
      <div className="section__entete">
        <h2 id="titre-loyers-a-encaisser">Loyers à encaisser</h2>
      </div>
      {loyers.length === 0 ? (
        <div className="tableau__action-corps">
          <p className="tableau__action-texte">Aucune échéance à afficher.</p>
          <Link to="/espace/locations" className="tableau__action-lien">
            Ajouter une location →
          </Link>
        </div>
      ) : (
        <div className="tableau__action-corps">
          <ul className="tableau__lignes">
            {loyers.slice(0, 3).map((loyer) => (
              <li className="tableau__ligne" key={loyer.id}>
                <span className="tableau__nom">{loyer.titre_bien || 'Bien immobilier'}</span>
                <span className="tableau__montant">{formaterNombre(loyer.montant_du || 0)} TND</span>
                <span className="tableau__date">Échéance {dateCourte(loyer.date_echeance)}</span>
                <span className={`tableau__statut ${CLASSES_LOYER[loyer.statut] || ''}`}>
                  {LIBELLES_LOYER[loyer.statut] || loyer.statut}
                </span>
              </li>
            ))}
          </ul>
          <Link to="/espace/locations" className="tableau__action-lien">
            Voir les locations →
          </Link>
        </div>
      )}
    </section>
  )
}

function CarteAFaire({ nbBrouillons = 0 }) {
  return (
    <section className="panneau tableau__action-carte" aria-labelledby="titre-a-faire">
      <div className="section__entete">
        <h2 id="titre-a-faire">À faire</h2>
      </div>
      <div className="tableau__action-corps">
        <p className="tableau__action-texte">
          <span className="tableau__badge-brouillon">{nbBrouillons} brouillon{nbBrouillons > 1 ? 's' : ''}</span>{' '}
          à publier
        </p>
        <Link to="/espace/annonces" className="tableau__action-lien">
          Compléter l'annonce →
        </Link>
      </div>
    </section>
  )
}

/** Tableau de bord de l'espace propriétaire : indicateurs, rendez-vous, loyers et activité récente. */
export default function TableauDeBordPage() {
  const { etat, donnees: stats, erreur, reessayer } = useRequete('statistiques', obtenirStatistiques)

  return (
    <section className="page tableau">
      <div className="page__entete tableau__entete-top">
        <h1>Tableau de bord</h1>
        <Link to="/espace/annonces/nouvelle" className="bouton bouton--principal tableau__btn-nouvelle">
          + Nouvelle annonce
        </Link>
      </div>

      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement des statistiques…
        </p>
      )}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && (
        <>
          {/* Bandeau d'activité synthétique "À traiter" */}
          <div className="tableau__banniere-a-traiter">
            <div className="tableau__banniere-items">
              <span className="tableau__banniere-titre">À traiter</span>
              <span className="tableau__banniere-item">{stats.visites_en_attente ?? 0} visite en attente</span>
              <span className="tableau__banniere-item">{stats.loyers_en_retard ?? 0} loyer en retard</span>
              <span className="tableau__banniere-item">{stats.transactions_en_cours ?? 0} transaction en cours</span>
              <span className="tableau__banniere-item">{stats.reclamations_ouvertes ?? 0} réclamation</span>
            </div>
            <div className="tableau__banniere-badge">
              <span className="badge-vert-pilule">Tout est à jour</span>
            </div>
          </div>

          {/* 5 Chiffres clés */}
          <div className="chiffres tableau__chiffres">
            <CarteChiffre libelle="Annonces" valeur={stats.total} />
            <CarteChiffre libelle="Publiées" valeur={stats.par_statut?.publiee ?? 0} />
            <CarteChiffre libelle="Brouillons" valeur={stats.par_statut?.brouillon ?? 0} />
            <CarteChiffre libelle="Loyer moyen" valeur={prixOuTiret(stats.prix_moyen?.location, 'location')} />
            <CarteChiffre libelle="Prix de vente moyen" valeur={prixOuTiret(stats.prix_moyen?.vente, 'vente')} />
            <CarteChiffre libelle="Maintenances ouvertes" valeur={stats.maintenances_ouvertes ?? 0} />
            <CarteChiffre libelle="Urgentes" valeur={stats.maintenances_urgentes ?? 0} />
          </div>

          {/* Répartitions : Donut pour le statut et Barres pour le type de bien */}
          <div className="panneaux tableau__repartitions">
            <Repartition titre="Annonces par statut" typeVisuel="donut" valeurs={enValeurs(stats.par_statut, LIBELLES_STATUT)} />
            <Repartition titre="Annonces par type de bien" typeVisuel="barres" valeurs={enValeurs(stats.par_type, LIBELLES_TYPE_BIEN)} />
          </div>

          <CarteChaleurAbsences donnees={stats.taux_absence_jour_heure} />

          {/* 3 Cartes d'action : Visites, Loyers, À faire */}
          <div className="panneaux tableau__actions-grille">
            <ListeVisites visites={stats.prochaines_visites} />
            <ListeLoyers loyers={stats.loyers_a_encaisser} />
            <CarteAFaire nbBrouillons={stats.par_statut?.brouillon ?? 1} />
          </div>

          {/* Dernières actions */}
          <section className="panneau tableau__dernieres-actions" aria-labelledby="titre-dernieres-actions">
            <div className="section__entete">
              <h2 id="titre-dernieres-actions">Dernières actions</h2>
              <Link to="/espace/historique">Voir tout l'historique →</Link>
            </div>
            {stats.dernieres_actions?.length === 0 ? (
              <p className="etat">Aucune action enregistrée pour le moment.</p>
            ) : (
              <ol className="historique__liste">
                {(stats.dernieres_actions || []).map((entree) => (
                  <li key={entree.id}>
                    <EntreeHistorique entree={entree} />
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </section>
  )
}
