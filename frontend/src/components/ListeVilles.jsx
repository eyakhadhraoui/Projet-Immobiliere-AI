import useVilles from '../hooks/useVilles'

/**
 * Liste déroulante des villes connues, reliée à un champ texte par `list={id}` : les villes sont filtrées
 * pendant la frappe et un clic remplit le champ. La saisie libre d'une autre ville reste possible.
 */
export default function ListeVilles({ id }) {
  const villes = useVilles()
  return (
    <datalist id={id}>
      {villes.map((ville) => (
        <option key={ville.nom} value={ville.nom} label={`${ville.nom} (${ville.nb_annonces} annonce${ville.nb_annonces > 1 ? 's' : ''} de référence)`} />
      ))}
    </datalist>
  )
}
