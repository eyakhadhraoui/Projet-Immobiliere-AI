import { useId, useState } from 'react'
import { envoyerPhotoProfil, retirerPhotoProfil } from '../api/auth'
import { lireErreur } from '../api/annonces'
import { useAuth } from '../hooks/useAuth'
import { EXTENSIONS_AUTORISEES, TAILLE_MAX_ENVOI, formaterTaille } from '../utils/photos'
import ApercuFichier from './ApercuFichier'
import Avatar from './Avatar'

function erreurFichier(fichier) {
  const extension = fichier.name.includes('.') ? fichier.name.split('.').pop().toLowerCase() : ''
  if (!EXTENSIONS_AUTORISEES.includes(extension)) {
    return `${fichier.name} : format non accepté (formats autorisés : ${EXTENSIONS_AUTORISEES.join(', ')}).`
  }
  if (fichier.size > TAILLE_MAX_ENVOI) {
    return `${fichier.name} pèse ${formaterTaille(fichier.size)} : ${formaterTaille(TAILLE_MAX_ENVOI)} maximum.`
  }
  return null
}

/** Photo de profil : aperçu avant envoi, envoi, suppression (mêmes contrôles que les photos d'annonces). */
export default function ProfilPhoto() {
  const { utilisateur, remplacerUtilisateur } = useAuth()
  const [fichier, setFichier] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const idSelecteur = useId()

  function choisir(event) {
    const choisi = event.target.files?.[0]
    event.target.value = ''
    setMessage(null)
    if (!choisi) return
    const probleme = erreurFichier(choisi)
    setErreur(probleme)
    setFichier(probleme ? null : choisi)
  }

  async function executer(action, succes) {
    setOccupe(true)
    setErreur(null)
    try {
      remplacerUtilisateur(await action())
      setFichier(null)
      setMessage(succes)
    } catch (error) {
      const { message: texte, champs } = lireErreur(error)
      setErreur(champs.photo?.join(' ') ?? texte)
    } finally {
      setOccupe(false)
    }
  }

  return (
    <section className="panneau profil__section" aria-labelledby="titre-photo">
      <h2 id="titre-photo">Photo de profil</h2>
      <div className="profil-photo">
        {fichier ? (
          <span className="avatar avatar--grand profil-photo__apercu">
            <ApercuFichier fichier={fichier} />
          </span>
        ) : (
          <Avatar utilisateur={utilisateur} taille="grand" texteAlternatif="Votre photo de profil actuelle" />
        )}
        <div className="profil-photo__actions">
          <div className="champ">
            <label htmlFor={idSelecteur}>Choisir une nouvelle photo</label>
            <input id={idSelecteur} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              onChange={choisir} disabled={occupe} />
            <p className="champ__aide">Formats {EXTENSIONS_AUTORISEES.join(', ')} ; {formaterTaille(TAILLE_MAX_ENVOI)} maximum.</p>
          </div>
          <div className="profil-photo__boutons">
            {fichier && (
              <>
                <button type="button" className="bouton bouton--principal" disabled={occupe}
                  onClick={() => executer(() => envoyerPhotoProfil(fichier), 'Photo de profil mise à jour.')}>
                  {occupe ? 'Envoi…' : 'Enregistrer la photo'}
                </button>
                <button type="button" className="bouton" onClick={() => setFichier(null)} disabled={occupe}>
                  Annuler
                </button>
              </>
            )}
            {!fichier && utilisateur.photo_profil && (
              <button type="button" className="bouton bouton--danger" disabled={occupe}
                onClick={() => executer(retirerPhotoProfil, 'Photo de profil retirée.')}>
                Retirer la photo
              </button>
            )}
          </div>
        </div>
      </div>
      {erreur && (
        <p className="champ__erreur" role="alert">
          {erreur}
        </p>
      )}
      {message && (
        <p className="message-succes" role="status">
          {message}
        </p>
      )}
    </section>
  )
}
