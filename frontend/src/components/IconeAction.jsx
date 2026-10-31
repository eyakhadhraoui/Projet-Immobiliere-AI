/** Tracés SVG (24×24, trait) d'une icône par type d'action de l'historique. */
const TRACES = {
  creation: 'M12 5v14M5 12h14',
  modification: 'M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4',
  changement_statut: 'M4 8h13l-3-3M20 16H7l3 3',
  ajout_photos: 'M3 6h12v12H3zM3 15l4-4 4 4M18 3v6M15 6h6',
  suppression_photo: 'M3 6h12v12H3zM3 15l4-4 4 4M15 6h6',
  reordonnancement_photos: 'M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4',
  suppression: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
}

/** Icône décorative d'une action (le libellé de l'action est toujours affiché à côté). */
export default function IconeAction({ action }) {
  return (
    <svg className="icone-action" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={TRACES[action] ?? 'M12 8v5M12 16h.01'} />
    </svg>
  )
}
