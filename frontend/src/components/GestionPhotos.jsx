import { useId, useState } from 'react'
import { lireErreur } from '../api/annonces'
import { ACCEPT_IMAGES, EXTENSIONS_AUTORISEES, MAX_PHOTOS, TAILLE_MAX_ENVOI, formaterTaille, verifierSelection } from '../utils/photos'
import ApercuFichier from './ApercuFichier'
import FenetreConfirmation from './FenetreConfirmation'

/**
 * Photos d'une annonce.
 * - photos : photos déjà enregistrées (suppression et ordre, si onSupprimerPhoto / onReordonner sont fournis) ;
 * - fichiers / onChangerFichiers : images choisies, vérifiées et prévisualisées, envoyées par le parent
 *   à l'enregistrement du formulaire.
 * onSupprimerPhoto(photo) et onReordonner(ids) renvoient une promesse rejetée en cas d'échec.
 */
export default function GestionPhotos({
  photos = [],
  fichiers,
  onChangerFichiers,
  onSupprimerPhoto,
  onReordonner,
}) {
  const [erreursSelection, setErreursSelection] = useState([])
  const [erreurAction, setErreurAction] = useState(null)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [photoASupprimer, setPhotoASupprimer] = useState(null)
  const idSelecteur = useId()
  const idConsignes = useId()

  const total = photos.length + fichiers.length

  function choisirFichiers(event) {
    const selection = [...event.target.files]
    event.target.value = '' // permet de rechoisir le même fichier après l'avoir retiré
    if (selection.length === 0) return
    const erreurs = verifierSelection(selection, photos.length, fichiers)
    setErreursSelection(erreurs)
    setMessage(null)
    if (erreurs.length === 0) onChangerFichiers([...fichiers, ...selection])
  }

  function retirerFichier(index) {
    onChangerFichiers(fichiers.filter((_, i) => i !== index))
    setErreursSelection([])
  }

  async function executer(action, messageSucces) {
    setOccupe(true)
    setErreurAction(null)
    setMessage(null)
    try {
      await action()
      setMessage(messageSucces)
      return true
    } catch (error) {
      setErreurAction(lireErreur(error).message)
      return false
    } finally {
      setOccupe(false)
    }
  }

  function deplacer(index, decalage) {
    const ids = photos.map((photo) => photo.id)
    ;[ids[index], ids[index + decalage]] = [ids[index + decalage], ids[index]]
    executer(() => onReordonner(ids), "Ordre des photos enregistré.")
  }

  async function confirmerSuppression() {
    const reussi = await executer(() => onSupprimerPhoto(photoASupprimer), 'Photo supprimée.')
    if (reussi) setPhotoASupprimer(null)
  }

  return (
    <fieldset className="formulaire__groupe photos">
      <legend>
        Photos ({total}/{MAX_PHOTOS})
      </legend>

      {photos.length > 0 && (
        <>
          <h3 className="photos__titre">Photos enregistrées</h3>
          <ol className="photos__liste">
            {photos.map((photo, index) => (
              <li key={photo.id} className="photos__element">
                <img src={photo.url} alt={`Photo ${index + 1} de l'annonce`} />
                <span className="photos__rang">{index === 0 ? 'Principale' : `n° ${index + 1}`}</span>
                {(onReordonner || onSupprimerPhoto) && (
                  <div className="photos__actions">
                    {onReordonner && (
                      <>
                        <button
                          type="button"
                          className="bouton bouton--petit"
                          onClick={() => deplacer(index, -1)}
                          disabled={occupe || index === 0}
                          aria-label={`Monter la photo ${index + 1}`}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="bouton bouton--petit"
                          onClick={() => deplacer(index, 1)}
                          disabled={occupe || index === photos.length - 1}
                          aria-label={`Descendre la photo ${index + 1}`}
                        >
                          ↓
                        </button>
                      </>
                    )}
                    {onSupprimerPhoto && (
                      <button
                        type="button"
                        className="bouton bouton--petit bouton--danger"
                        onClick={() => setPhotoASupprimer(photo)}
                        disabled={occupe}
                        aria-label={`Supprimer la photo ${index + 1}`}
                      >
                        Supprimer
                      </button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </>
      )}

      <div className="champ">
        <label htmlFor={idSelecteur}>Ajouter des photos</label>
        <input
          id={idSelecteur}
          type="file"
          multiple
          accept={ACCEPT_IMAGES}
          onChange={choisirFichiers}
          disabled={occupe || total >= MAX_PHOTOS}
          aria-describedby={idConsignes}
          aria-invalid={erreursSelection.length > 0 ? 'true' : undefined}
        />
        <p className="champ__aide" id={idConsignes}>
          Formats {EXTENSIONS_AUTORISEES.join(', ')} ; {MAX_PHOTOS} photos maximum par annonce ;{' '}
          {formaterTaille(TAILLE_MAX_ENVOI)} maximum par envoi.
        </p>
      </div>

      {erreursSelection.length > 0 && (
        <ul className="champ__erreur" role="alert">
          {erreursSelection.map((erreur) => (
            <li key={erreur}>{erreur}</li>
          ))}
        </ul>
      )}

      {fichiers.length > 0 && (
        <>
          <h3 className="photos__titre">Photos à envoyer à l'enregistrement</h3>
          <ul className="photos__liste">
            {fichiers.map((fichier, index) => (
              <li key={`${index}-${fichier.name}-${fichier.size}`} className="photos__element">
                <ApercuFichier fichier={fichier} />
                <span className="photos__rang">{fichier.name}</span>
                <div className="photos__actions">
                  <button
                    type="button"
                    className="bouton bouton--petit"
                    onClick={() => retirerFichier(index)}
                    disabled={occupe}
                    aria-label={`Retirer ${fichier.name}`}
                  >
                    Retirer
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {erreurAction && !photoASupprimer && (
        <p className="champ__erreur" role="alert">
          {erreurAction}
        </p>
      )}
      {message && (
        <p className="message-succes" role="status">
          {message}
        </p>
      )}

      {photoASupprimer && (
        <FenetreConfirmation
          titre="Supprimer cette photo ?"
          message="La photo sera définitivement supprimée de l'annonce."
          libelleConfirmer="Supprimer la photo"
          libelleEnCours="Suppression…"
          enCours={occupe}
          erreur={erreurAction}
          onConfirmer={confirmerSuppression}
          onAnnuler={() => {
            setPhotoASupprimer(null)
            setErreurAction(null)
          }}
        />
      )}
    </fieldset>
  )
}
