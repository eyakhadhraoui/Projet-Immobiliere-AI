import { useRef, useState } from 'react'
import { CARACTERISTIQUES, CHAMPS_FORMULAIRE, VALEURS_VIDES, validerAnnonce, versApi } from '../utils/annonceForm'
import { LIBELLES_TRANSACTION, LIBELLES_TYPE_BIEN } from '../utils/format'
import Champ from './Champ'
import EstimationPrix from './EstimationPrix'
import ListeVilles from './ListeVilles'
import { genererDescriptionAnnonce } from '../api/annonces'
import DisponibilitesVisite from './DisponibilitesVisite'

/**
 * Formulaire d'annonce, commun à la création et à la modification.
 *
 * onSoumettre reçoit le corps API (validé côté client) et renvoie une promesse :
 * null en cas de succès (le parent navigue), ou { message, champs } (format de lireErreur)
 * pour afficher les erreurs de l'API sous les champs.
 * children s'affiche avant le bouton (ex. gestion des photos).
 */
export default function AnnonceForm({ valeursInitiales = VALEURS_VIDES, onSoumettre, libelleBouton, children }) {
  const [valeurs, setValeurs] = useState(valeursInitiales)
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [iaEnCours, setIaEnCours] = useState(false)
  const [erreurIa, setErreurIa] = useState('')
  const formulaire = useRef(null)

  function effacerErreur(champ) {
    setErreurs((precedentes) => {
      if (!precedentes[champ]) return precedentes
      const { [champ]: _supprime, ...autres } = precedentes
      return autres
    })
  }

  function modifier(event) {
    const { name, value, type, checked } = event.target
    setValeurs((precedentes) => ({ ...precedentes, [name]: type === 'checkbox' ? checked : value }))
    effacerErreur(name)
  }

  function utiliserPrixEstime(prix) {
    setValeurs((precedentes) => ({ ...precedentes, prix: String(prix) }))
    effacerErreur('prix')
  }

  function basculerCaracteristique(event) {
    const { value, checked } = event.target
    setValeurs((precedentes) => ({
      ...precedentes,
      caracteristiques: checked
        ? [...precedentes.caracteristiques, value]
        : precedentes.caracteristiques.filter((c) => c !== value),
    }))
    effacerErreur('caracteristiques')
  }

  function placerFocusSurPremiereErreur() {
    // Après le rendu des erreurs : le lecteur d'écran annonce le champ et son message.
    requestAnimationFrame(() => formulaire.current?.querySelector('[aria-invalid="true"]')?.focus())
  }

  async function demanderDescription(action) {
    setIaEnCours(true)
    setErreurIa('')
    try {
      const description = await genererDescriptionAnnonce({ ...valeurs, action })
      setValeurs((precedentes) => ({ ...precedentes, description }))
      effacerErreur('description')
    } catch (error) {
      setErreurIa(error.response?.data?.message || 'Impossible de générer la description. Vérifiez Gemini et réessayez.')
    } finally {
      setIaEnCours(false)
    }
  }

  async function soumettre(event) {
    event.preventDefault()
    setErreurGenerale(null)
    const erreursClient = validerAnnonce(valeurs)
    setErreurs(erreursClient)
    if (Object.keys(erreursClient).length > 0) {
      setErreurGenerale({ message: 'Le formulaire contient des erreurs : corrigez les champs signalés.', autres: [] })
      placerFocusSurPremiereErreur()
      return
    }

    setEnvoiEnCours(true)
    const echec = await onSoumettre(versApi(valeurs), valeurs.disponibilites)
    setEnvoiEnCours(false)
    if (echec) {
      const champs = echec.champs ?? {}
      setErreurs(champs)
      // Erreurs de l'API sur des champs absents du formulaire (ex. owner_id) : affichées en tête.
      const autres = Object.entries(champs).filter(([champ]) => !CHAMPS_FORMULAIRE.includes(champ))
      setErreurGenerale({ message: echec.message, autres })
      placerFocusSurPremiereErreur()
    }
  }

  const proprietes = (nom) => ({ value: valeurs[nom], onChange: modifier })

  return (
    <form ref={formulaire} className="formulaire" onSubmit={soumettre} noValidate aria-busy={envoiEnCours}>
      {erreurGenerale && (
        <div className="etat etat--erreur formulaire__alerte" role="alert">
          <p>{erreurGenerale.message}</p>
          {erreurGenerale.autres.length > 0 && (
            <ul>
              {erreurGenerale.autres.map(([champ, messages]) => (
                <li key={champ}>
                  <strong>{champ}</strong> : {messages.join(' ')}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <fieldset className="formulaire__groupe">
        <legend>Description</legend>
        <Champ nom="titre" libelle="Titre *" erreurs={erreurs.titre} aide="Entre 5 et 150 caractères.">
          {(aria) => <input {...aria} {...proprietes('titre')} type="text" maxLength={150} />}
        </Champ>
        <Champ nom="description" libelle="Description *" erreurs={erreurs.description}>
          {(aria) => <textarea {...aria} {...proprietes('description')} rows={5} />}
        </Champ>
        <div className="formulaire__actions">
          <button type="button" className="bouton bouton--secondaire" disabled={iaEnCours || envoiEnCours} onClick={() => demanderDescription('generer')}>
            {iaEnCours ? 'Génération…' : 'Générer avec Gemini'}
          </button>
          <button type="button" className="bouton bouton--secondaire" disabled={iaEnCours || envoiEnCours || !valeurs.description.trim()} onClick={() => demanderDescription('ameliorer')}>
            Améliorer la description
          </button>
        </div>
        {erreurIa && <p className="etat etat--erreur" role="alert">{erreurIa}</p>}
      </fieldset>

      <fieldset className="formulaire__groupe formulaire__grille">
        <legend>Bien</legend>
        <Champ nom="type_bien" libelle="Type de bien *" erreurs={erreurs.type_bien}>
          {(aria) => (
            <select {...aria} {...proprietes('type_bien')}>
              <option value="">Choisir…</option>
              {Object.entries(LIBELLES_TYPE_BIEN).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          )}
        </Champ>
        <Champ nom="transaction" libelle="Transaction *" erreurs={erreurs.transaction}>
          {(aria) => (
            <select {...aria} {...proprietes('transaction')}>
              <option value="">Choisir…</option>
              {Object.entries(LIBELLES_TRANSACTION).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          )}
        </Champ>
        <Champ
          nom="prix"
          libelle="Prix (TND) *"
          erreurs={erreurs.prix}
          aide={valeurs.transaction === 'location' ? 'Loyer mensuel.' : undefined}
        >
          {(aria) => <input {...aria} {...proprietes('prix')} type="number" min="0" step="any" inputMode="decimal" />}
        </Champ>
        <Champ nom="surface" libelle="Surface (m²) *" erreurs={erreurs.surface}>
          {(aria) => <input {...aria} {...proprietes('surface')} type="number" min="0" step="any" inputMode="decimal" />}
        </Champ>
        <Champ nom="nb_pieces" libelle="Nombre de pièces *" erreurs={erreurs.nb_pieces}>
          {(aria) => <input {...aria} {...proprietes('nb_pieces')} type="number" min="0" step="1" inputMode="numeric" />}
        </Champ>
        <div className="champ champ--case">
          <input id="champ-meuble" name="meuble" type="checkbox" checked={valeurs.meuble} onChange={modifier} />
          <label htmlFor="champ-meuble">Meublé</label>
        </div>
      </fieldset>

      <DisponibilitesVisite
        valeur={valeurs.disponibilites}
        onChange={(disponibilites) => setValeurs((precedentes) => ({ ...precedentes, disponibilites }))}
      />

      <EstimationPrix valeurs={valeurs} prixActuel={valeurs.prix} onUtiliserPrix={utiliserPrixEstime} />

      <fieldset className="formulaire__groupe formulaire__grille">
        <legend>Localisation</legend>
        <Champ nom="adresse" libelle="Adresse *" erreurs={erreurs.adresse}>
          {(aria) => <input {...aria} {...proprietes('adresse')} type="text" maxLength={255} autoComplete="street-address" />}
        </Champ>
        <Champ nom="ville" libelle="Ville *" erreurs={erreurs.ville} aide="Commencez à taper puis choisissez dans la liste : une ville connue rend l’estimation plus fiable.">
          {(aria) => (
            <>
              <input {...aria} {...proprietes('ville')} type="text" maxLength={100} list="villes-annonce" autoComplete="off" />
              <ListeVilles id="villes-annonce" />
            </>
          )}
        </Champ>
        <Champ nom="latitude" libelle="Latitude (facultative)" erreurs={erreurs.latitude} aide="Entre -90 et 90.">
          {(aria) => <input {...aria} {...proprietes('latitude')} type="number" step="any" inputMode="decimal" />}
        </Champ>
        <Champ nom="longitude" libelle="Longitude (facultative)" erreurs={erreurs.longitude} aide="Entre -180 et 180.">
          {(aria) => <input {...aria} {...proprietes('longitude')} type="number" step="any" inputMode="decimal" />}
        </Champ>
      </fieldset>

      <fieldset
        className="formulaire__groupe"
        aria-invalid={erreurs.caracteristiques ? 'true' : undefined}
        aria-describedby={erreurs.caracteristiques ? 'erreur-caracteristiques' : undefined}
      >
        <legend>Caractéristiques</legend>
        <div className="cases">
          {Object.entries(CARACTERISTIQUES).map(([valeur, libelle]) => (
            <div key={valeur} className="champ--case">
              <input
                id={`caracteristique-${valeur}`}
                type="checkbox"
                value={valeur}
                checked={valeurs.caracteristiques.includes(valeur)}
                onChange={basculerCaracteristique}
              />
              <label htmlFor={`caracteristique-${valeur}`}>{libelle}</label>
            </div>
          ))}
        </div>
        {erreurs.caracteristiques && (
          <p className="champ__erreur" id="erreur-caracteristiques">
            {erreurs.caracteristiques.join(' ')}
          </p>
        )}
      </fieldset>

      {children && (
        // Bloque aussi les contrôles fournis par le parent (photos) pendant l'envoi.
        <fieldset className="formulaire__extra" disabled={envoiEnCours}>
          {children}
        </fieldset>
      )}

      <div className="formulaire__actions">
        <button type="submit" className="bouton bouton--principal" disabled={envoiEnCours}>
          {envoiEnCours ? 'Envoi en cours…' : libelleBouton}
        </button>
      </div>
    </form>
  )
}
