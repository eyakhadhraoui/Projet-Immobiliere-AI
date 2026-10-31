import { useLocation } from 'react-router-dom'

/** Affiche l'URL courante (data-testid="url") pour vérifier les redirections dans les tests. */
export default function UrlCourante() {
  const { pathname, search } = useLocation()
  return <span data-testid="url">{pathname + search}</span>
}
