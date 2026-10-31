import { useEffect } from 'react'

/**
 * Boîte de dialogue accessible pour confirmer une action irréversible (ex. suppression).
 *
 * @param {object} props
 * @param {boolean} props.ouvert Est-ce que la boîte est visible ?
 * @param {string} props.titre Titre de la confirmation
 * @param {string} props.message Message d'avertissement
 * @param {string} [props.texteConfirmer='Supprimer'] Libellé du bouton rouge de confirmation
 * @param {() => void} props.onConfirmer Action exécutée lors de la confirmation
 * @param {() => void} props.onAnnuler Action d'annulation / fermeture
 * @param {boolean} [props.chargement=false] Indicateur de traitement en cours
 */
export default function ModalConfirmation({
  ouvert,
  titre,
  message,
  texteConfirmer = 'Supprimer',
  onConfirmer,
  onAnnuler,
  chargement = false,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && ouvert && !chargement) {
        onAnnuler()
      }
    }
    if (ouvert) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [ouvert, chargement, onAnnuler])

  if (!ouvert) return null

  return (
    <div className="modale-overlay" role="dialog" aria-modal="true" aria-labelledby="titre-modale-conf">
      <div className="modale-boite">
        <h3 id="titre-modale-conf" className="modale-titre">
          ⚠️ {titre}
        </h3>
        <p className="modale-message">{message}</p>
        <div className="modale-actions">
          <button
            type="button"
            className="bouton bouton--secondaire"
            onClick={onAnnuler}
            disabled={chargement}
          >
            Annuler
          </button>
          <button
            type="button"
            className="bouton bouton--danger"
            onClick={onConfirmer}
            disabled={chargement}
          >
            {chargement ? 'Suppression…' : texteConfirmer}
          </button>
        </div>
      </div>
    </div>
  )
}
