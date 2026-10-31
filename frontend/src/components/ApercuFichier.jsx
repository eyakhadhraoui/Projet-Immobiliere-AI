import { useEffect, useRef } from 'react'

/** Aperçu local d'une image choisie mais pas encore envoyée. */
export default function ApercuFichier({ fichier }) {
  const image = useRef(null)

  // URL temporaire vers le fichier local, posée sur l'image puis libérée quand l'aperçu disparaît.
  useEffect(() => {
    const urlLocale = URL.createObjectURL(fichier)
    image.current.src = urlLocale
    return () => URL.revokeObjectURL(urlLocale)
  }, [fichier])

  return <img ref={image} alt={`Aperçu : ${fichier.name}`} />
}
