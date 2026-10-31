/**
 * Navigation précédent / suivant avec numéro de page et nombre total d'éléments.
 * unite : [singulier, pluriel] de ce qui est compté (annonces par défaut).
 */
export default function Pagination({ page, totalPages, total, onChangerPage, unite = ['annonce', 'annonces'] }) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" className="bouton" onClick={() => onChangerPage(page - 1)} disabled={page <= 1}>
        ← Précédent
      </button>
      <p className="pagination__info">
        Page {page} sur {Math.max(totalPages, 1)} · {total} {total > 1 ? unite[1] : unite[0]}
      </p>
      <button type="button" className="bouton" onClick={() => onChangerPage(page + 1)} disabled={page >= totalPages}>
        Suivant →
      </button>
    </nav>
  )
}
