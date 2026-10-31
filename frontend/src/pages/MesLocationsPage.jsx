import { Link } from 'react-router-dom'
import { locationsActivesMaintenance } from '../api/maintenance'
import { useRequete } from '../hooks/useRequete'

export default function MesLocationsPage() {
  const { donnees: locations, etat, erreur, reessayer } = useRequete('mes-locations-actives', locationsActivesMaintenance)
  return <section className="page espace-page mes-locations-page">
    <header className="page__entete espace-page__entete"><div><h1>Mes locations</h1><p className="texte-secondaire">Consultez vos baux actifs et signalez rapidement un problème à votre propriétaire.</p></div></header>
    {etat === 'chargement' && <p className="etat" role="status">Chargement de vos locations…</p>}
    {etat === 'erreur' && <div className="etat etat--erreur" role="alert"><p>{erreur?.message || 'Impossible de charger vos locations.'}</p><button className="bouton" onClick={reessayer}>Réessayer</button></div>}
    {etat === 'succes' && locations.length === 0 && <div className="panneau espace-page__vide"><span className="espace-page__vide-icone" aria-hidden="true">🔑</span><h2>Aucune location active</h2><p>Les contrats actifs apparaîtront ici. Seuls ces biens peuvent recevoir un signalement de maintenance.</p><Link className="bouton bouton--principal" to="/annonces">Parcourir les annonces</Link></div>}
    {etat === 'succes' && locations.length > 0 && <div className="mes-locations__grille">{locations.map((location) => <article key={location.id} className="panneau mes-locations__carte">
      <div><span className="maintenance-badge maintenance-badge--vert">Bail actif</span><h2>{location.titre}</h2><p>{location.ville}</p></div>
      <dl><div><dt>Référence</dt><dd>{location.reference}</dd></div><div><dt>Loyer mensuel</dt><dd>{Number(location.loyer_mensuel).toLocaleString('fr-FR')} TND</dd></div><div><dt>Propriétaire</dt><dd>{location.proprietaire_nom}</dd></div></dl>
      <Link className="bouton bouton--principal" to={`/maintenance?location_id=${location.id}`}>Signaler un problème</Link>
    </article>)}</div>}
  </section>
}
