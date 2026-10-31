import { initiales } from '../utils/compte'

/**
 * Photo de profil, ou initiales sur fond coloré s'il n'y en a pas.
 * Décoratif par défaut (le nom est écrit à côté) ; texteAlternatif le rend lisible par les lecteurs d'écran.
 */
export default function Avatar({ utilisateur, taille = 'moyen', texteAlternatif = '' }) {
  const classe = `avatar avatar--${taille}`
  if (utilisateur?.photo_profil) {
    return <img className={classe} src={utilisateur.photo_profil} alt={texteAlternatif} />
  }
  return (
    <span className={`${classe} avatar--initiales`} role={texteAlternatif ? 'img' : undefined}
      aria-label={texteAlternatif || undefined} aria-hidden={texteAlternatif ? undefined : 'true'}>
      {initiales(utilisateur)}
    </span>
  )
}
