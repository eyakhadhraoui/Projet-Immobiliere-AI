import { useId } from 'react'

const COULEURS_STATUT = {
  publiee: '#1d5fbf',
  brouillon: '#f59e0b',
  en_attente: '#64748b',
  louee: '#10b981',
  vendue: '#6366f1',
}

/**
 * Répartition statistique (donut pour le statut, barres horizontales pour le type de bien).
 * @param {object} props
 * @param {string} props.titre Titre de la section
 * @param {Array<{cle: string, libelle: string, nombre: number}>} props.valeurs Données
 * @param {'auto'|'donut'|'barres'} [props.typeVisuel='auto']
 */
export default function Repartition({ titre, valeurs, typeVisuel = 'auto' }) {
  const idTitre = useId()
  const total = valeurs.reduce((somme, { nombre }) => somme + nombre, 0)
  const estDonut = typeVisuel === 'donut' || (typeVisuel === 'auto' && titre.toLowerCase().includes('statut'))

  // Calcul des segments du donut SVG
  const rayon = 38
  const circonference = 2 * Math.PI * rayon
  let offsetCumule = 0

  const segments = estDonut && total > 0
    ? valeurs
        .filter((v) => v.nombre > 0)
        .map((v) => {
          const ratio = v.nombre / total
          const dash = ratio * circonference
          const segment = {
            cle: v.cle,
            dash,
            offset: offsetCumule,
            couleur: COULEURS_STATUT[v.cle] || '#1d5fbf',
          }
          offsetCumule += dash
          return segment
        })
    : []

  return (
    <section className={`panneau repartition-panneau ${estDonut ? 'repartition-panneau--donut' : 'repartition-panneau--barres'}`} aria-labelledby={idTitre}>
      <h2 id={idTitre}>{titre}</h2>
      <div className={`repartition__corps ${estDonut ? 'repartition__corps--donut' : ''}`}>
        {estDonut && (
          <div className="repartition__donut-visuel" aria-hidden="true">
            <svg viewBox="0 0 100 100" className="repartition__donut-svg">
              {total === 0 ? (
                <circle cx="50" cy="50" r={rayon} fill="none" stroke="var(--media-fond, #e2e8f0)" strokeWidth="13" />
              ) : (
                segments.map((s) => (
                  <circle
                    key={s.cle}
                    cx="50"
                    cy="50"
                    r={rayon}
                    fill="none"
                    stroke={s.couleur}
                    strokeWidth="13"
                    strokeDasharray={`${s.dash} ${circonference}`}
                    strokeDashoffset={-s.offset}
                    transform="rotate(-90 50 50)"
                  />
                ))
              )}
              <text x="50" y="55" textAnchor="middle" className="repartition__donut-total">
                {total}
              </text>
            </svg>
          </div>
        )}

        <ul className={`repartition ${estDonut ? 'repartition--donut' : 'repartition--barres'}`}>
          {valeurs.map(({ cle, libelle, nombre }) => {
            const pourcentage = total > 0 ? Math.round((nombre / total) * 100) : 0
            return (
              <li key={cle} className={`repartition__ligne repartition__ligne--${cle}`}>
                <span className="repartition__libelle">{libelle}</span>
                <span className="repartition__barre" aria-hidden="true">
                  <span style={{ width: `${pourcentage}%` }} />
                </span>
                <span className="repartition__nombre">
                  {nombre} <span className="repartition__pourcentage">({pourcentage} %)</span>
                </span>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
