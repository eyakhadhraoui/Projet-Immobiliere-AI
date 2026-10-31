import { useState } from 'react'
import { NOMS_ACTIONS } from '../utils/historique'

/**
 * Filtres de la page historique (annonce, type d'action, période), appliqués à la validation.
 * Le parent la remonte (prop key) quand l'URL change, pour resynchroniser les champs.
 */
export default function FiltresHistorique({ valeurs, annonces, onAppliquer, onReinitialiser }) {
  const [saisie, setSaisie] = useState(valeurs)

  function modifier(event) {
    const { name, value } = event.target
    setSaisie((precedente) => ({ ...precedente, [name]: value }))
  }

  function soumettre(event) {
    event.preventDefault()
    onAppliquer(saisie)
  }

  // Annonce filtrée absente de la liste (ex. supprimée) : on la propose quand même.
  const annonceInconnue = saisie.annonce_id && !annonces.some((a) => String(a.id) === saisie.annonce_id)

  return (
    <form className="filtres" onSubmit={soumettre} aria-label="Filtrer l'historique">
      <div className="champ">
        <label htmlFor="historique-annonce">Annonce</label>
        <select id="historique-annonce" name="annonce_id" value={saisie.annonce_id} onChange={modifier}>
          <option value="">Toutes les annonces</option>
          {annonceInconnue && <option value={saisie.annonce_id}>Annonce n° {saisie.annonce_id}</option>}
          {annonces.map((annonce) => (
            <option key={annonce.id} value={String(annonce.id)}>
              {annonce.titre}
            </option>
          ))}
        </select>
      </div>
      <div className="champ">
        <label htmlFor="historique-action">Type d'action</label>
        <select id="historique-action" name="action" value={saisie.action} onChange={modifier}>
          <option value="">Toutes les actions</option>
          {Object.entries(NOMS_ACTIONS).map(([valeur, libelle]) => (
            <option key={valeur} value={valeur}>
              {libelle}
            </option>
          ))}
        </select>
      </div>
      <div className="champ">
        <label htmlFor="historique-debut">Du</label>
        <input id="historique-debut" name="date_debut" type="date" value={saisie.date_debut} onChange={modifier} />
      </div>
      <div className="champ">
        <label htmlFor="historique-fin">Au</label>
        <input id="historique-fin" name="date_fin" type="date" value={saisie.date_fin} onChange={modifier} />
      </div>
      <div className="filtres__actions">
        <button type="submit" className="bouton bouton--principal">
          Filtrer
        </button>
        <button type="button" className="bouton" onClick={onReinitialiser}>
          Réinitialiser
        </button>
      </div>
    </form>
  )
}
