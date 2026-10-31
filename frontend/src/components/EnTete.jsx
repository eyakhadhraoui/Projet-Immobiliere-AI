import { Link, NavLink } from 'react-router-dom'
import { NOM_SITE } from '../constantes'
import { useAuth } from '../hooks/useAuth'
import MenuUtilisateur from './MenuUtilisateur'
import LienNotificationsMaintenance from './LienNotificationsMaintenance'

/**
 * En-tête du site : logo texte, navigation principale, puis menu du compte (connecté)
 * ou boutons Connexion / Inscription (visiteur).
 * « Espace propriétaire » est masqué pour les comptes clients, qui n'y ont pas accès.
 */
export default function EnTete() {
  const { utilisateur, chargement } = useAuth()
  const afficherEspace = !utilisateur || utilisateur.role === 'proprietaire'
  const estLocataire = utilisateur?.role === 'client'

  return (
    <header className="entete">
      <div className="entete__interieur">
        <Link to="/" className="entete__marque">
          <svg className="entete__logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10M10 19.5v-5h4v5" />
          </svg>
          {NOM_SITE}
        </Link>
        <nav aria-label="Navigation principale">
          <ul className="entete__liens">
            <li>
              <NavLink to="/" end className="entete__lien">
                Accueil
              </NavLink>
            </li>
            <li>
              <NavLink to="/annonces" className="entete__lien">
                Annonces
              </NavLink>
            </li>
            <li>
              <NavLink to="/visites" className="entete__lien">
                Visites
              </NavLink>
            </li>
            {estLocataire && <li><NavLink to="/mes-locations" className="entete__lien">Mes locations</NavLink></li>}
            {estLocataire && <li><NavLink to="/maintenance" className="entete__lien">Maintenance</NavLink></li>}
            {utilisateur && <li><NavLink to="/dossiers-litige" className="entete__lien">Dossiers litige</NavLink></li>}
            {afficherEspace && (
              <li>
                <NavLink to="/espace" className="entete__lien entete__lien--espace">
                  Espace propriétaire
                </NavLink>
              </li>
            )}
          </ul>
        </nav>
        <div className="entete__compte">
          <div className="entete__langues" aria-label="Langue">
            <span className="entete__langue entete__langue--actif">FR</span>
            <span className="entete__langue-sep">|</span>
            <span className="entete__langue">AR</span>
          </div>
          {!chargement && utilisateur && <MenuUtilisateur />}
          {!chargement && utilisateur && <LienNotificationsMaintenance />}
          {!chargement && !utilisateur && (
            <>
              <Link to="/connexion" className="bouton bouton--texte">
                Connexion
              </Link>
              <Link to="/inscription" className="bouton bouton--principal">
                Inscription
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
