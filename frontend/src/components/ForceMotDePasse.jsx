import { LIBELLES_NIVEAU, evaluerMotDePasse } from '../utils/motDePasse'

const SEGMENTS = { vide: 0, faible: 1, moyen: 2, fort: 3 }

/**
 * Indicateur de force du mot de passe : barre en 3 segments, niveau écrit en toutes lettres
 * et liste des critères (cochés / non cochés) — la couleur n'est jamais la seule information.
 */
export default function ForceMotDePasse({ motDePasse, id }) {
  const { niveau, criteres } = evaluerMotDePasse(motDePasse)
  return (
    <div className={`force force--${niveau}`} id={id}>
      <div className="force__barre" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={n <= SEGMENTS[niveau] ? 'force__segment force__segment--plein' : 'force__segment'} />
        ))}
      </div>
      <p className="force__niveau" aria-live="polite">
        {niveau === 'vide' ? 'Choisissez un mot de passe.' : `Force : ${LIBELLES_NIVEAU[niveau]}`}
      </p>
      <ul className="force__criteres">
        {criteres.map((critere) => (
          <li key={critere.id} className={critere.ok ? 'force__critere force__critere--ok' : 'force__critere'}>
            <span aria-hidden="true">{critere.ok ? '✓' : '○'}</span> {critere.libelle}
            {!critere.obligatoire && <span className="force__conseil"> (conseillé)</span>}
            <span className="visuellement-cache">{critere.ok ? ' : respecté' : ' : non respecté'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
