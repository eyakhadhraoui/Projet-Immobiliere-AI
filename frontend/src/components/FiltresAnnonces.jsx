import { useState } from 'react'
import { LIBELLES_TRANSACTION, LIBELLES_TYPE_BIEN } from '../utils/format'
import ListeVilles from './ListeVilles'

/**
 * Barre de filtres. Les valeurs saisies ne sont appliquées (et écrites dans l'URL)
 * qu'à la validation du formulaire, pour éviter un appel API à chaque frappe.
 * Le parent la remonte (prop key) quand l'URL change, pour resynchroniser les champs.
 */
export default function FiltresAnnonces({ valeurs, onAppliquer, onReinitialiser }) {
  const [saisie, setSaisie] = useState(valeurs)

  function modifier(event) {
    const { name, value } = event.target
    setSaisie((precedente) => ({ ...precedente, [name]: value }))
  }

  function soumettre(event) {
    event.preventDefault()
    onAppliquer(saisie)
  }

  return (
    <form className="filtres" onSubmit={soumettre} role="search" aria-label="Filtrer les annonces">
      <div className="champ">
        <label htmlFor="filtre-ville">Ville</label>
        <input id="filtre-ville" name="ville" type="text" value={saisie.ville} onChange={modifier} placeholder="Ex. Tunis" list="villes-filtres" autoComplete="off" />
        <ListeVilles id="villes-filtres" />
      </div>

      <div className="champ">
        <label htmlFor="filtre-type-bien">Type de bien</label>
        <select id="filtre-type-bien" name="type_bien" value={saisie.type_bien} onChange={modifier}>
          <option value="">Tous</option>
          {Object.entries(LIBELLES_TYPE_BIEN).map(([valeur, libelle]) => (
            <option key={valeur} value={valeur}>
              {libelle}
            </option>
          ))}
        </select>
      </div>

      <div className="champ">
        <label htmlFor="filtre-transaction">Transaction</label>
        <select id="filtre-transaction" name="transaction" value={saisie.transaction} onChange={modifier}>
          <option value="">Toutes</option>
          {Object.entries(LIBELLES_TRANSACTION).map(([valeur, libelle]) => (
            <option key={valeur} value={valeur}>
              {libelle}
            </option>
          ))}
        </select>
      </div>

      <div className="champ">
        <label htmlFor="filtre-prix-min">Prix min (TND)</label>
        <input id="filtre-prix-min" name="prix_min" type="number" min="0" inputMode="numeric" value={saisie.prix_min} onChange={modifier} />
      </div>

      <div className="champ">
        <label htmlFor="filtre-prix-max">Prix max (TND)</label>
        <input id="filtre-prix-max" name="prix_max" type="number" min="0" inputMode="numeric" value={saisie.prix_max} onChange={modifier} />
      </div>

      <div className="champ">
        <label htmlFor="filtre-meuble">Meublé</label>
        <select id="filtre-meuble" name="meuble" value={saisie.meuble} onChange={modifier}>
          <option value="">Indifférent</option>
          <option value="true">Oui</option>
          <option value="false">Non</option>
        </select>
      </div>

      <div className="champ">
        <label htmlFor="filtre-tri">Trier les annonces</label>
        <select id="filtre-tri" name="tri" value={saisie.tri || 'chronologique'} onChange={modifier}>
          <option value="chronologique">Plus récentes</option>
          <option value="pertinence">Compatibilité avec ma recherche</option>
        </select>
      </div>

      <div className="filtres__actions">
        <button type="submit" className="bouton bouton--principal">
          Rechercher
        </button>
        <button type="button" className="bouton" onClick={onReinitialiser}>
          Réinitialiser
        </button>
      </div>
    </form>
  )
}
