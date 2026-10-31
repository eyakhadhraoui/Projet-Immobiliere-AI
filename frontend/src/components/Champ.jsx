/**
 * Libellé + contrôle + messages d'erreur d'un champ de formulaire.
 * children reçoit les attributs à poser sur le contrôle (id, aria-invalid, aria-describedby).
 * Ex. erreur sur "prix" → <p class="champ__erreur" id="erreur-prix"> et aria-describedby="erreur-prix".
 */
export default function Champ({ nom, libelle, erreurs = [], aide, children }) {
  const idControle = `champ-${nom}`
  const idErreur = `erreur-${nom}`
  const idAide = `aide-${nom}`
  const enErreur = erreurs.length > 0
  const decritPar = [aide && idAide, enErreur && idErreur].filter(Boolean).join(' ')

  return (
    <div className={`champ${enErreur ? ' champ--erreur' : ''}`}>
      <label htmlFor={idControle}>{libelle}</label>
      {children({
        id: idControle,
        name: nom,
        'aria-invalid': enErreur ? 'true' : undefined,
        'aria-describedby': decritPar || undefined,
      })}
      {aide && (
        <p className="champ__aide" id={idAide}>
          {aide}
        </p>
      )}
      {enErreur && (
        <p className="champ__erreur" id={idErreur}>
          {erreurs.join(' ')}
        </p>
      )}
    </div>
  )
}
