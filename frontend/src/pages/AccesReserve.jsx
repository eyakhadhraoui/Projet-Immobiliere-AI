import { Link } from 'react-router-dom'

/** Page affichée à un compte client qui ouvre l'espace propriétaire. */
export default function AccesReserve() {
  return (
    <section className="page page--introuvable">
      <h1>Espace réservé aux propriétaires</h1>
      <p>Votre compte est un compte client : l'espace propriétaire sert à publier et gérer des annonces.</p>
      <Link to="/">← Retour à l'accueil</Link>
    </section>
  )
}
