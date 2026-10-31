import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Affiche les messages transmis lors d'une navigation :
 * navigate(url, { state: { succes: '…', avertissement: '…' } }).
 */
export default function BandeauMessages() {
  const location = useLocation()
  const navigate = useNavigate()
  const { succes, avertissement } = location.state ?? {}

  if (!succes && !avertissement) return null

  function fermer() {
    // Retire les messages de l'historique : ils ne réapparaissent pas après un rafraîchissement.
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null })
  }

  return (
    <div className="bandeau">
      {succes && (
        <p className="bandeau__message bandeau__message--succes" role="status">
          {succes}
        </p>
      )}
      {avertissement && (
        <p className="bandeau__message bandeau__message--avertissement" role="alert">
          {avertissement}
        </p>
      )}
      <button type="button" className="bouton bouton--petit" onClick={fermer} aria-label="Fermer le message">
        ×
      </button>
    </div>
  )
}
