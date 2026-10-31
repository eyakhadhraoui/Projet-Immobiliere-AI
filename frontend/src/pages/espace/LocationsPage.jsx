import { useState } from 'react'
import { Link } from 'react-router-dom'
import { encaisserLoyerLocation, listerLocations } from '../../api/locations'
import MessageErreur from '../../components/MessageErreur'
import { useRequete } from '../../hooks/useRequete'
import { formaterNombre } from '../../utils/format'

const STATUTS = {
  brouillon: 'Brouillon', en_attente_signature: 'En attente de signature', active: 'Active',
  en_preavis: 'En préavis', terminee: 'Terminée', resiliee: 'Résiliée', impayee: 'Impayée',
}

function dateFr(iso) {
  if (!iso) return '—'
  const [annee, mois, jour] = String(iso).slice(0, 10).split('-')
  return annee && mois && jour ? `${jour}/${mois}/${annee}` : iso
}

/** Liste des baux du propriétaire et des échéances de loyer correspondantes. */
export default function LocationsPage() {
  const { etat, donnees, erreur, reessayer, modifierDonnees } = useRequete('locations', () => listerLocations({ page: 1, per_page: 50 }))
  const [erreurAction, setErreurAction] = useState('')
  const [enCours, setEnCours] = useState(null)
  const contrats = donnees?.items || []
  const contratsActifs = contrats.filter((location) => location.statut === 'active')
  const loyersDus = contrats.flatMap((location) => location.loyers || []).filter((loyer) => loyer.statut !== 'paye')
  const montantDu = loyersDus.reduce((total, loyer) => total + Number(loyer.montant_du || 0), 0)
  const retards = loyersDus.filter((loyer) => loyer.statut === 'en_retard')

  async function encaisser(locationId, loyerId) {
    setEnCours(loyerId)
    setErreurAction('')
    try {
      const maj = await encaisserLoyerLocation(locationId, loyerId)
      modifierDonnees((precedent) => ({
        ...precedent,
        items: precedent.items.map((location) => location.id === locationId
          ? { ...location, loyers: location.loyers.map((loyer) => loyer.id === loyerId ? maj : loyer) }
          : location),
      }))
    } catch (error) {
      setErreurAction(error.response?.data?.message || 'Impossible d’enregistrer le paiement.')
    } finally {
      setEnCours(null)
    }
  }

  return (
    <section className="page espace-page espace-page--locations">
      <div className="page__entete espace-page__entete">
        <div><h1>Gestion des locations</h1><p className="texte-secondaire">Contrats de bail et suivi des échéances de loyer.</p></div>
        <Link to="/annonces" className="bouton bouton--principal">+ Nouveau contrat</Link>
      </div>
      {etat === 'succes' && <div className="espace-page__stats">
        <article><span>Contrats actifs</span><strong>{contratsActifs.length}</strong></article>
        <article><span>Loyers à encaisser</span><strong>{formaterNombre(montantDu)} TND</strong></article>
        <article><span>Loyers en retard</span><strong className="stat--danger">{retards.length}</strong></article>
        <article><span>Taux d’occupation</span><strong className="stat--succes">{contrats.length ? Math.round(contratsActifs.length / contrats.length * 100) : 0} %</strong></article>
      </div>}
      {etat === 'chargement' && <p className="etat" role="status">Chargement des contrats…</p>}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}
      {erreurAction && <p role="alert" className="etat etat--erreur">{erreurAction}</p>}
      {etat === 'succes' && (contrats.length === 0
        ? <div className="panneau etat-vide espace-page__vide"><span className="espace-page__vide-icone" aria-hidden="true">🔑</span><h2>Aucun contrat de location</h2><p>Créez un contrat pour suivre les échéances et recevoir des rappels de loyer.</p><Link to="/annonces" className="bouton bouton--principal">+ Nouveau contrat</Link><Link to="/annonces">Parcourir les annonces à louer →</Link></div>
        : <div className="locations__liste">
            {contrats.map((location) => <article className="panneau locations__contrat" key={location.id}>
              <div className="page__entete">
                <div><p className="locations__reference">{location.reference}</p><h2><Link to={`/espace/locations/${location.id}`}>{location.titre_annonce}</Link></h2><p className="texte-secondaire">{location.ville_annonce} · Locataire : {location.locataire_nom}</p></div>
                <span className="badge badge--publiee">{STATUTS[location.statut] || location.statut}</span>
              </div>
              <p><strong>{formaterNombre(location.loyer_mensuel)} TND/mois</strong> · Du {dateFr(location.date_debut)} au {dateFr(location.date_fin)}</p>
              {location.statut === 'active' && <Link className="bouton bouton--secondaire" to={`/maintenance?location_id=${location.id}`}>Signaler un problème</Link>}
              <h3>Échéances de loyer</h3>
              <ul className="locations__loyers">
                {(location.loyers || []).map((loyer) => <li key={loyer.id}>
                  <span>{loyer.periode?.slice(0, 7)} · {formaterNombre(loyer.montant_du)} TND</span>
                  <span className={`locations__statut locations__statut--${loyer.statut}`}>{loyer.statut === 'paye' ? 'Payé' : loyer.statut === 'en_retard' ? 'En retard' : loyer.statut === 'partiel' ? 'Partiel' : 'À payer'}</span>
                  {loyer.statut !== 'paye' && <button type="button" className="bouton" onClick={() => encaisser(location.id, loyer.id)} disabled={enCours === loyer.id}>{enCours === loyer.id ? 'Enregistrement…' : 'Encaisser'}</button>}
                </li>)}
              </ul>
            </article>)}
          </div>)}
    </section>
  )
}
