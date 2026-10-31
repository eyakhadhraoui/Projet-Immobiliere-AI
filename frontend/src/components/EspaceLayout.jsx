import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { listerReclamations } from '../api/reclamations'
import { useRequete } from '../hooks/useRequete'

/**
 * Mise en page de l'espace propriétaire : menu latéral + contenu de la page.
 * Sur petit écran, le menu est replié derrière un bouton « Menu ».
 */
export default function EspaceLayout() {
  const { pathname } = useLocation()
  const [menuOuvert, setMenuOuvert] = useState(false)
  const { donnees: reclamationsNouvelles } = useRequete('reclamations-menu-nouvelles', () => listerReclamations({ statut: 'nouvelle', page: 1, per_page: 1 }))
  const nombreNouvelles = reclamationsNouvelles?.total || 0
  const fermer = () => setMenuOuvert(false)

  // « Mes annonces » reste actif sur le détail et la modification, mais pas sur « Nouvelle annonce ».
  const mesAnnoncesActif = pathname.startsWith('/espace/annonces') && pathname !== '/espace/annonces/nouvelle'
  const visitesActif = pathname.startsWith('/espace/visites')
  const transactionsActif = pathname.startsWith('/espace/transactions')
  const reclamationsActif = pathname.startsWith('/espace/reclamations')
  const locationsActif = pathname.startsWith('/espace/locations')
  const maintenanceActif = pathname.startsWith('/espace/maintenance')
  const classe = (actif) => `espace__lien${actif ? ' active' : ''}`

  return (
    <div className="espace">
      <aside className="espace__barre">
        <button
          type="button"
          className="bouton espace__bouton-menu"
          aria-expanded={menuOuvert}
          aria-controls="menu-espace"
          onClick={() => setMenuOuvert((ouvert) => !ouvert)}
        >
          <span aria-hidden="true">☰</span> Menu de l'espace
        </button>
        <nav id="menu-espace" className="espace__menu" data-ouvert={menuOuvert} aria-label="Espace propriétaire">
          <p className="espace__titre">Espace propriétaire</p>
          <ul>
            <li>
              <NavLink to="/espace" end className={({ isActive }) => classe(isActive)} onClick={fermer}>
                <span aria-hidden="true">▦ </span>Tableau de bord
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/espace/annonces"
                className={() => classe(mesAnnoncesActif)}
                aria-current={mesAnnoncesActif ? 'page' : undefined}
                onClick={fermer}
              >
                <span aria-hidden="true">🏘 </span>Mes annonces
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/espace/visites"
                className={() => classe(visitesActif)}
                aria-current={visitesActif ? 'page' : undefined}
                onClick={fermer}
              >
                <span><span aria-hidden="true">🗓 </span>Visites</span>
                <span className="espace__badge-notif">2</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/espace/transactions"
                className={() => classe(transactionsActif)}
                aria-current={transactionsActif ? 'page' : undefined}
                onClick={fermer}
              >
                <span aria-hidden="true">🤝 </span>Transactions
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/espace/reclamations"
                className={() => classe(reclamationsActif)}
                aria-current={reclamationsActif ? 'page' : undefined}
                onClick={fermer}
              >
                <span><span aria-hidden="true">⚠ </span>Réclamations</span>
                {nombreNouvelles > 0 && <span className="espace__badge-notif" aria-label={`${nombreNouvelles} nouvelles réclamations`}>{nombreNouvelles}</span>}
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/espace/locations"
                className={() => classe(locationsActif)}
                aria-current={locationsActif ? 'page' : undefined}
                onClick={fermer}
              >
                <span aria-hidden="true">🔑 </span>Locations
              </NavLink>
            </li>
            <li>
              <NavLink to="/espace/maintenance" className={() => classe(maintenanceActif && !pathname.endsWith('/notifications'))} aria-current={maintenanceActif && !pathname.endsWith('/notifications') ? 'page' : undefined} onClick={fermer}>
                <span aria-hidden="true">🛠 </span>Maintenance
              </NavLink>
            </li>
            <li>
              <NavLink to="/espace/maintenance/notifications" className={() => classe(pathname.endsWith('/notifications'))} onClick={fermer}>
                <span aria-hidden="true">🔔 </span>Notifications
              </NavLink>
            </li>
            <li>
              <NavLink to="/espace/historique" className={({ isActive }) => classe(isActive)} onClick={fermer}>
                <span aria-hidden="true">◷ </span>Historique
              </NavLink>
            </li>
          </ul>
        </nav>
      </aside>
      <div className="espace__contenu">
        <Outlet />
      </div>
    </div>
  )
}
