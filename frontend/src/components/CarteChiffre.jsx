/** Carte de chiffre clé du tableau de bord (ex. « Publiées : 3 »). */
export default function CarteChiffre({ libelle, valeur, complement }) {
  return (
    <div className="chiffre">
      <p className="chiffre__libelle">{libelle}</p>
      <p className="chiffre__valeur">{valeur}</p>
      {complement && <p className="chiffre__complement">{complement}</p>}
    </div>
  )
}
