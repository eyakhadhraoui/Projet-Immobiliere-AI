import { Link } from 'react-router-dom'
import { NOM_SITE } from '../constantes'
import { useAuth } from '../hooks/useAuth'

const ANNEE = new Date().getFullYear() // calculée une fois, pas à chaque rendu

/** Pied de page du site. */
export default function PiedDePage() {
  const { utilisateur } = useAuth()
  const afficherEspace = !utilisateur || utilisateur.role === 'proprietaire' // comme l'en-tête
  return (
    <footer className="pied">
      <div className="pied__interieur">
        <div>
          <p className="pied__marque">{NOM_SITE}</p>
          <p className="pied__texte">Annonces immobilières à louer et à vendre.</p>
        </div>
        <nav aria-label="Liens du pied de page">
          <ul className="pied__liens">
            <li>
              <Link to="/">Accueil</Link>
            </li>
            <li>
              <Link to="/annonces">Toutes les annonces</Link>
            </li>
            {afficherEspace && (
              <li>
                <Link to="/espace">Espace propriétaire</Link>
              </li>
            )}
          </ul>
        </nav>
      </div>
      <p className="pied__copyright">© {ANNEE} {NOM_SITE}</p>
    </footer>
  )
}
