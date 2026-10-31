import { Link } from 'react-router-dom'
import { listerNotificationsMaintenance, marquerNotificationMaintenanceLue } from '../api/maintenance'
import { useAuth } from '../hooks/useAuth'
import { useRequete } from '../hooks/useRequete'

export default function MaintenanceNotificationsPage() {
  const { utilisateur } = useAuth()
  const retour = utilisateur?.role === 'proprietaire' ? '/espace/maintenance' : '/maintenance'
  const { donnees, etat, erreur, reessayer } = useRequete('maintenance-notifications', listerNotificationsMaintenance)
  async function ouvrir(notification) {
    if (!notification.lue) await marquerNotificationMaintenanceLue(notification.id)
    reessayer()
  }
  return <section className="page espace-page maintenance-page"><header className="page__entete espace-page__entete"><div><h1>Notifications et historique</h1><p className="texte-secondaire">Les changements de statut sont notifiés aux deux parties et conservés dans l’historique.</p></div><Link to={retour}>← Retour</Link></header>
    {etat === 'chargement' && <p className="etat">Chargement…</p>}{etat === 'erreur' && <p className="etat etat--erreur">{erreur?.message}</p>}
    {etat === 'succes' && <section className="panneau maintenance__notifications"><h2>🔔 Notifications · {utilisateur?.role === 'proprietaire' ? 'propriétaire' : 'locataire'}</h2>{donnees.items.length ? donnees.items.map((item) => <Link className={!item.lue ? 'non-lue' : ''} key={item.id} to={utilisateur?.role === 'proprietaire' ? `/espace/maintenance/${item.demande_id}` : `/maintenance/${item.demande_id}`} onClick={() => ouvrir(item)}><span aria-hidden="true">{item.lue ? '✓' : '🔔'}</span><strong>{item.message}</strong><time>{new Date(item.date_creation).toLocaleString('fr-FR')}</time></Link>) : <p>Aucune notification pour le moment.</p>}</section>}
  </section>
}
