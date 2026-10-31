import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import AccesReserve from '../pages/AccesReserve'
import { urlConnexion } from '../utils/compte'

/**
 * Affiche children seulement pour un utilisateur connecté (et du bon rôle si role est précisé).
 * Visiteur → page de connexion, avec retour à la page demandée après connexion.
 */
export default function RouteProtegee({ role, children }) {
  const { utilisateur, chargement } = useAuth()
  const { pathname, search } = useLocation()

  if (chargement) {
    return (
      <p className="etat" role="status">
        Vérification de la session…
      </p>
    )
  }
  if (!utilisateur) return <Navigate to={urlConnexion(pathname + search)} replace />
  if (role && utilisateur.role !== role) return <AccesReserve />
  return children
}
