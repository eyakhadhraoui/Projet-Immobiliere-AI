import { useEffect, useId, useRef } from 'react'

/**
 * Fenêtre modale de confirmation. Le focus va sur « Annuler » à l'ouverture
 * (action sans risque) ; Échap ferme la fenêtre.
 */
export default function FenetreConfirmation({
  titre,
  message,
  libelleConfirmer = 'Confirmer',
  libelleEnCours = 'Veuillez patienter…',
  enCours = false,
  erreur = null,
  onConfirmer,
  onAnnuler,
}) {
  const idTitre = useId()
  const idMessage = useId()
  const boutonAnnuler = useRef(null)

  useEffect(() => {
    boutonAnnuler.current?.focus()
  }, [])

  function gererTouche(event) {
    if (event.key === 'Escape' && !enCours) onAnnuler()
  }

  return (
    <div className="fenetre__fond" onKeyDown={gererTouche}>
      <div className="fenetre" role="alertdialog" aria-modal="true" aria-labelledby={idTitre} aria-describedby={idMessage}>
        <h2 id={idTitre}>{titre}</h2>
        <p id={idMessage}>{message}</p>
        {erreur && (
          <p className="champ__erreur" role="alert">
            {erreur}
          </p>
        )}
        <div className="fenetre__actions">
          <button ref={boutonAnnuler} type="button" className="bouton" onClick={onAnnuler} disabled={enCours}>
            Annuler
          </button>
          <button type="button" className="bouton bouton--danger" onClick={onConfirmer} disabled={enCours}>
            {enCours ? libelleEnCours : libelleConfirmer}
          </button>
        </div>
      </div>
    </div>
  )
}
