import { Link } from 'react-router-dom'

const LIEN_PAR_DEFAUT = { to: '/annonces', libelle: '← Retour à la liste des annonces' }

/** Page 404 (adresse inconnue, annonce inexistante ou non publiée). */
export default function PageIntrouvable({
  titre = 'Page introuvable',
  message = "Cette adresse ne correspond à aucune page.",
  lien = LIEN_PAR_DEFAUT,
}) {
  return (
    <section className="page page--introuvable">
      <h1>{titre}</h1>
      <p>{message}</p>
      <Link to={lien.to}>{lien.libelle}</Link>
    </section>
  )
}
