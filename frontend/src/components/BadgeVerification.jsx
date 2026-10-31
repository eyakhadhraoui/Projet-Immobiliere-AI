/** Badge d'une vérification d'identité (« CIN vérifiée », « Visage vérifié »), écrit en toutes lettres. */
export default function BadgeVerification({ libelle, verifie }) {
  return (
    <span className={`badge-verification ${verifie ? 'badge-verification--ok' : 'badge-verification--attente'}`}>
      <span aria-hidden="true">{verifie ? '✓' : '…'}</span> {libelle} : {verifie ? 'vérifié' : 'non vérifié'}
    </span>
  )
}
