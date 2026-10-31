import AnnonceCarte from './AnnonceCarte'
import Pagination from './Pagination'

/** Grille des cartes + pagination, ou message si aucun résultat. */
export default function ListeAnnonces({ donnees, filtresActifs, onReinitialiser, onChangerPage }) {
  const { items, page, per_page: parPage, total } = donnees
  const totalPages = Math.ceil(total / parPage)

  if (total === 0) {
    return (
      <div className="etat etat--vide" role="status">
        <p>Aucune annonce ne correspond à votre recherche.</p>
        {filtresActifs && (
          <button type="button" className="bouton" onClick={onReinitialiser}>
            Effacer les filtres
          </button>
        )}
      </div>
    )
  }

  return (
    <>
      {donnees.tri_demande === 'pertinence' && (
        <p className="page__intro" role="status">
          {donnees.tri_applique === 'pertinence'
            ? 'Classement expérimental : il s’appuie sur des données simulées; aucun gain significatif n’est démontré sur de vrais visiteurs.'
            : 'Le classement intelligent est indisponible; les annonces sont présentées de la plus récente à la plus ancienne.'}
        </p>
      )}
      {items.length === 0 ? (
        // Page demandée au-delà de la dernière (ex. ?page=9 alors qu'il n'y en a que 2).
        <p className="etat etat--vide" role="status">
          Aucune annonce sur cette page.
        </p>
      ) : (
        <ul className="grille" aria-label="Liste des annonces">
          {items.map((annonce) => (
            <li key={annonce.id}>
              <AnnonceCarte annonce={annonce} />
            </li>
          ))}
        </ul>
      )}
      <Pagination page={page} totalPages={totalPages} total={total} onChangerPage={onChangerPage} />
    </>
  )
}
