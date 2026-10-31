import { useState } from 'react'
import photoIndisponible from '../assets/photo-indisponible.svg'

/** Photo principale + miniatures cliquables pour changer la photo affichée. */
export default function Galerie({ photos, titre }) {
  const [indexActif, setIndexActif] = useState(0)

  if (photos.length === 0) {
    return (
      <div className="galerie">
        <img className="galerie__principale" src={photoIndisponible} alt="Aucune photo disponible" />
      </div>
    )
  }

  const index = Math.min(indexActif, photos.length - 1)

  return (
    <div className="galerie">
      <img
        className="galerie__principale"
        src={photos[index].url}
        alt={`${titre} — photo ${index + 1} sur ${photos.length}`}
      />
      {photos.length > 1 && (
        <ul className="galerie__miniatures" aria-label="Miniatures">
          {photos.map((photo, i) => (
            <li key={photo.id}>
              <button
                type="button"
                className="galerie__miniature"
                onClick={() => setIndexActif(i)}
                aria-label={`Afficher la photo ${i + 1}`}
                aria-pressed={i === index}
              >
                <img src={photo.url} alt="" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
