/** En-tête de colonne triable : un clic trie, un second clic inverse le sens. */
export default function EnteteTri({ colonne, libelle, tri, onTrier }) {
  const actif = tri.colonne === colonne
  const sensAria = actif ? (tri.sens === 'asc' ? 'ascending' : 'descending') : 'none'
  const prochain = actif && tri.sens === 'asc' ? 'décroissant' : 'croissant'

  return (
    <th scope="col" aria-sort={sensAria}>
      <button
        type="button"
        className="tri"
        onClick={() => onTrier(colonne)}
        title={`Trier par ${libelle.toLowerCase()} (ordre ${prochain})`}
      >
        {libelle}
        <span className="tri__fleche" aria-hidden="true">
          {actif ? (tri.sens === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}
