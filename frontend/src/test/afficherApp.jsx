import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import FournisseurAuth from '../contexts/FournisseurAuth'
import { PROPRIETAIRE_CONNECTE } from './donnees'
import UrlCourante from './UrlCourante'

/**
 * Rend toute l'application à l'URL donnée, avec un routeur en mémoire.
 *
 * @param {string} url Page de départ.
 * @param {{ utilisateur?: object | null }} options Session de départ : propriétaire connecté par défaut
 *   (les pages de l'espace sont réservées aux propriétaires depuis USER-002), null pour un visiteur.
 */
export function afficherApp(url, { utilisateur = PROPRIETAIRE_CONNECTE } = {}) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <FournisseurAuth utilisateurInitial={utilisateur}>
        <App />
        <UrlCourante />
      </FournisseurAuth>
    </MemoryRouter>,
  )
}
