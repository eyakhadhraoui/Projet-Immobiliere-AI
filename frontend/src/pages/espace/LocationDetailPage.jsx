import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listerMaintenance } from '../../api/maintenance'
import { encaisserLoyerLocation, obtenirLocation } from '../../api/locations'
import MessageErreur from '../../components/MessageErreur'
import { useRequete } from '../../hooks/useRequete'
import { formaterNombre } from '../../utils/format'

const STATUTS = { brouillon: 'Brouillon', en_attente_signature: 'En attente de signature', active: 'Active', en_preavis: 'En préavis', terminee: 'Terminée', resiliee: 'Résiliée', impayee: 'Impayée' }
const STATUTS_MAINTENANCE = { signalee: 'Signalée', acceptee: 'Acceptée', assignee: 'Assignée', planifiee: 'Planifiée', cloturee: 'Clôturée', refusee: 'Refusée' }
const OUVERTS = new Set(['signalee', 'acceptee', 'assignee', 'planifiee'])

function dateFr(iso) {
  if (!iso) return '—'
  const [annee, mois, jour] = String(iso).slice(0, 10).split('-')
  return annee && mois && jour ? `${jour}/${mois}/${annee}` : iso
}

export default function LocationDetailPage() {
  const { id } = useParams()
  const [onglet, setOnglet] = useState('resume')
  const [voirTout, setVoirTout] = useState(false)
  const [loyerEnCours, setLoyerEnCours] = useState(null)
  const [erreurAction, setErreurAction] = useState('')
  const { donnees: location, etat, erreur, reessayer, modifierDonnees } = useRequete(['location-detail', id], () => obtenirLocation(id))
  const { donnees: maintenance, etat: etatMaintenance, erreur: erreurMaintenance, reessayer: reessayerMaintenance } = useRequete(
    ['location-maintenance', id],
    () => listerMaintenance({ location_id: id, per_page: 50 }),
  )
  const loyers = useMemo(() => [...(location?.loyers || [])].sort((a, b) => (a.date_echeance || '').localeCompare(b.date_echeance || '')), [location?.loyers])
  const demandes = maintenance?.items || []
  const nbOuvertes = demandes.filter((demande) => OUVERTS.has(demande.statut)).length

  async function encaisser(loyerId) {
    setLoyerEnCours(loyerId)
    setErreurAction('')
    try {
      const maj = await encaisserLoyerLocation(location.id, loyerId)
      modifierDonnees((precedent) => ({ ...precedent, loyers: precedent.loyers.map((loyer) => loyer.id === loyerId ? maj : loyer) }))
    } catch (e) {
      setErreurAction(e.response?.data?.message || 'Impossible d’enregistrer le paiement.')
    } finally {
      setLoyerEnCours(null)
    }
  }

  if (etat === 'chargement') return <p className="etat" role="status">Chargement du contrat…</p>
  if (etat !== 'succes' || !location) return <section className="page"><MessageErreur erreur={erreur} onReessayer={reessayer} /></section>

  const echeancesVisibles = voirTout ? loyers : loyers.slice(0, 3)
  return <section className="page espace-page location-detail">
    <header className="page__entete espace-page__entete"><div><p className="location-detail__reference">{location.reference}</p><h1>{location.titre_annonce}</h1><p className="texte-secondaire">{location.ville_annonce} · Locataire : {location.locataire_nom}</p></div><span className={`badge ${location.statut === 'active' ? 'badge--vert' : 'badge--gris'}`}>{STATUTS[location.statut] || location.statut}</span></header>
    <div className="location-detail__barre"><Link to="/espace/locations">← Retour aux locations</Link>{location.statut === 'active' && <Link className="bouton bouton--principal" to={`/maintenance?location_id=${location.id}`}>Signaler un problème</Link>}</div>
    {erreurAction && <p className="etat etat--erreur" role="alert">{erreurAction}</p>}
    <div className="location-detail__onglets" role="tablist" aria-label="Détails du contrat">
      <button type="button" role="tab" aria-selected={onglet === 'resume'} className={onglet === 'resume' ? 'actif' : ''} onClick={() => setOnglet('resume')}>Résumé</button>
      <button type="button" role="tab" aria-selected={onglet === 'maintenance'} className={onglet === 'maintenance' ? 'actif' : ''} onClick={() => setOnglet('maintenance')}>Maintenance <span>{nbOuvertes}</span></button>
    </div>

    {onglet === 'resume' ? <>
      <article className="panneau location-detail__infos"><div><span>Loyer mensuel</span><strong>{formaterNombre(location.loyer_mensuel)} TND/mois</strong></div><div><span>Date de début</span><strong>{dateFr(location.date_debut)}</strong></div><div><span>Date de fin</span><strong>{dateFr(location.date_fin)}</strong></div><div><span>Type de contrat</span><strong>{location.type_location?.replaceAll('_', ' ')}</strong></div></article>
      <section className="panneau location-detail__echeances"><div className="section__entete"><h2>Échéances de loyer</h2><span>{loyers.length} échéance{loyers.length === 1 ? '' : 's'}</span></div>
        {echeancesVisibles.length === 0 ? <p className="etat">Aucune échéance enregistrée.</p> : <ul className="locations__loyers">{echeancesVisibles.map((loyer) => <li key={loyer.id}><span>{dateFr(loyer.date_echeance)} · {formaterNombre(loyer.montant_du)} TND</span><span className={`locations__statut locations__statut--${loyer.statut}`}>{loyer.statut === 'paye' ? 'Payé' : loyer.statut === 'en_retard' ? 'En retard' : loyer.statut === 'partiel' ? 'Partiel' : 'À payer'}</span>{loyer.statut !== 'paye' && <button type="button" className="bouton" onClick={() => encaisser(loyer.id)} disabled={loyerEnCours === loyer.id}>{loyerEnCours === loyer.id ? 'Enregistrement…' : 'Encaisser'}</button>}</li>)}</ul>}
        {loyers.length > 3 && <button type="button" className="location-detail__voir-plus" onClick={() => setVoirTout((visible) => !visible)}>{voirTout ? 'Réduire' : 'Voir les autres'}</button>}
      </section>
    </> : <section className="panneau location-detail__maintenance"><div className="section__entete"><div><h2>Demandes de maintenance</h2><p>{nbOuvertes} demande{nbOuvertes === 1 ? '' : 's'} ouverte{nbOuvertes === 1 ? '' : 's'}</p></div>{location.statut === 'active' && <Link className="bouton bouton--principal" to={`/maintenance?location_id=${location.id}`}>Signaler un problème</Link>}</div>
      {etatMaintenance === 'chargement' && <p className="etat" role="status">Chargement des demandes…</p>}
      {etatMaintenance === 'erreur' && <div className="etat etat--erreur"><p>{erreurMaintenance?.message || 'Impossible de charger les demandes.'}</p><button type="button" className="bouton" onClick={reessayerMaintenance}>Réessayer</button></div>}
      {etatMaintenance === 'succes' && demandes.length === 0 && <p className="etat">Aucune demande de maintenance liée à ce contrat.</p>}
      {etatMaintenance === 'succes' && demandes.length > 0 && <ul className="location-detail__demandes">{demandes.map((demande) => <li key={demande.id}><div><strong>{demande.titre}</strong><span>{demande.reference} · {dateFr(demande.date_creation)}</span></div><span className={`maintenance-badge maintenance-badge--${demande.statut === 'cloturee' ? 'vert' : demande.statut === 'refusee' ? 'rouge' : 'attente'}`}>{STATUTS_MAINTENANCE[demande.statut]}</span><Link to={`/espace/maintenance/${demande.id}`}>Détails</Link></li>)}</ul>}
    </section>}
  </section>
}
