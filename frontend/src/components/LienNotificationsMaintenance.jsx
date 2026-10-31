import { Link } from 'react-router-dom'
import { listerNotificationsMaintenance } from '../api/maintenance'
import { useAuth } from '../hooks/useAuth'
import { useRequete } from '../hooks/useRequete'

export default function LienNotificationsMaintenance() {
  const { utilisateur } = useAuth()
  const { donnees } = useRequete(['maintenance-notifications-header', utilisateur?.id], listerNotificationsMaintenance)
  const nombre = donnees?.non_lues || 0
  const lien = utilisateur?.role === 'proprietaire' ? '/espace/maintenance/notifications' : '/maintenance/notifications'
  return <Link className="maintenance__lien-notifications" to={lien} aria-label={`Notifications de maintenance${nombre ? `, ${nombre} non lues` : ''}`}>
    <span aria-hidden="true">🔔</span>{nombre > 0 && <b>{nombre > 99 ? '99+' : nombre}</b>}
  </Link>
}
