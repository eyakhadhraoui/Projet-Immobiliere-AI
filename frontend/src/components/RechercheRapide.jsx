import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { construireParams } from '../utils/filtresUrl'
import { LIBELLES_TYPE_BIEN } from '../utils/format'
import ListeVilles from './ListeVilles'

/** Recherche rapide de la page d'accueil : mène au catalogue filtré (/annonces?ville=…). */
export default function RechercheRapide() {
  const navigate = useNavigate()
  const [ongletTransaction, setOngletTransaction] = useState('vente')
  const [saisie, setSaisie] = useState({
    ville: '',
    type_bien: '',
    nb_pieces: '',
    prix_max: '',
    meuble: false,
    avec_photos: false,
  })

  function modifier(event) {
    const { name, value, type, checked } = event.target
    setSaisie((precedente) => ({
      ...precedente,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  function changerOnglet(transaction) {
    setOngletTransaction(transaction)
  }

  function toggleMeuble() {
    setSaisie((p) => ({ ...p, meuble: !p.meuble }))
  }

  function rechercher(event) {
    event.preventDefault()
    // Si l'utilisateur a cliqué sur Louer, on ajoute transaction=location
    const paramsAConstruire = { ...saisie }
    if (ongletTransaction === 'location') {
      paramsAConstruire.transaction = 'location'
    }
    // Nettoyer les valeurs vides
    if (!paramsAConstruire.nb_pieces) delete paramsAConstruire.nb_pieces
    if (!paramsAConstruire.meuble) delete paramsAConstruire.meuble
    if (!paramsAConstruire.avec_photos) delete paramsAConstruire.avec_photos

    const params = new URLSearchParams(construireParams(paramsAConstruire)).toString()
    navigate(params ? `/annonces?${params}` : '/annonces')
  }

  return (
    <div className="hero__recherche-conteneur">
      {/* Onglets Acheter / Louer */}
      <div className="hero__onglets" role="tablist" aria-label="Transaction">
        <button
          type="button"
          className={`hero__onglet ${ongletTransaction === 'vente' ? 'hero__onglet--actif' : ''}`}
          onClick={() => changerOnglet('vente')}
        >
          Acheter
        </button>
        <button
          type="button"
          className={`hero__onglet ${ongletTransaction === 'location' ? 'hero__onglet--actif' : ''}`}
          onClick={() => changerOnglet('location')}
        >
          Louer
        </button>
      </div>

      {/* Formulaire blanc arrondi */}
      <form className="recherche-rapide" onSubmit={rechercher} role="search" aria-label="Recherche rapide">
        <div className="champ">
          <label htmlFor="rapide-ville">Ville</label>
          <input
            id="rapide-ville"
            name="ville"
            type="text"
            value={saisie.ville}
            onChange={modifier}
            placeholder="Ex. Tunis, Sousse…"
            list="villes-recherche-rapide"
            autoComplete="off"
          />
          <ListeVilles id="villes-recherche-rapide" />
        </div>

        <div className="champ">
          <label htmlFor="rapide-type">Type de bien</label>
          <select id="rapide-type" name="type_bien" value={saisie.type_bien} onChange={modifier}>
            <option value="">Tous les types</option>
            {Object.entries(LIBELLES_TYPE_BIEN).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </div>

        <div className="champ">
          <label htmlFor="rapide-pieces">Pièces</label>
          <input
            id="rapide-pieces"
            name="nb_pieces"
            type="text"
            value={saisie.nb_pieces}
            onChange={modifier}
            placeholder="S+1, S+2, S+3…"
            autoComplete="off"
          />
        </div>

        <div className="champ">
          <label htmlFor="rapide-budget">Budget max (TND)</label>
          <input
            id="rapide-budget"
            name="prix_max"
            type="number"
            min="0"
            inputMode="numeric"
            value={saisie.prix_max}
            onChange={modifier}
            placeholder="250 000"
          />
        </div>

        <button type="submit" className="bouton bouton--principal recherche-rapide__bouton">
          Rechercher
        </button>
      </form>

      {/* Filtres secondaires sous le formulaire */}
      <div className="hero__puces-filtres">
        <button
          type="button"
          className={`hero__puce ${saisie.meuble ? 'hero__puce--actif' : ''}`}
          onClick={toggleMeuble}
        >
          Meublé
        </button>
        <button type="button" className="hero__puce">
          Surface min
        </button>
        <button type="button" className="hero__puce">
          Avec photos
        </button>
      </div>
    </div>
  )
}
