import { useState } from 'react'
import { Link } from 'react-router-dom'
import { lireErreur } from '../api/annonces'
import { rechercherVisites, creerVisite } from '../api/visites'
import { LIBELLES_TRANSACTION, LIBELLES_TYPE_BIEN, formaterPrix } from '../utils/format'

function dateDemain() {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function disponibiliteVide() {
  return { date: dateDemain(), debut: '09:00', fin: '12:00' }
}

function dateHeure(date, heure) {
  return `${date}T${heure}:00`
}

const LIBELLES_INFLUENCES = {
  ville_exacte: 'ville demandée',
  type_exact: 'type de bien',
  transaction_exacte: 'type de transaction',
  prix_dans_budget: 'prix dans le budget',
  ecart_prix: 'écart de prix',
  surface_suffisante: 'surface minimale',
  ecart_surface: 'écart de surface',
  meuble_exact: 'préférence meublé',
  prix_relatif_budget: 'prix relatif au budget',
  surface_confort: 'surface',
}

export default function VisitesRecherchePage() {
  const [criteres, setCriteres] = useState({
    villes: '', transaction: 'location', type_bien: '', budget_max: '', pieces_min: '', tri: 'pertinence',
  })
  const [disponibilites, setDisponibilites] = useState(() => [disponibiliteVide()])
  const [telephone, setTelephone] = useState('')
  const [chargement, setChargement] = useState(false)
  const [recherche, setRecherche] = useState(null)
  const [erreur, setErreur] = useState('')
  const [reservationEnCours, setReservationEnCours] = useState(null)
  const [message, setMessage] = useState('')

  function modifierCritere(event) {
    setCriteres((avant) => ({ ...avant, [event.target.name]: event.target.value }))
  }

  function modifierDisponibilite(index, champ, valeur) {
    setDisponibilites((avant) => avant.map((plage, i) => i === index ? { ...plage, [champ]: valeur } : plage))
  }

  async function lancerRecherche(event) {
    event.preventDefault()
    setChargement(true)
    setErreur('')
    setMessage('')
    try {
      const resultat = await rechercherVisites({
        villes: criteres.villes.split(',').map((ville) => ville.trim()).filter(Boolean),
        transaction: criteres.transaction || null,
        type_bien: criteres.type_bien || null,
        budget_max: criteres.budget_max ? Number(criteres.budget_max) : null,
        pieces_min: criteres.pieces_min ? Number(criteres.pieces_min) : null,
        tri: criteres.tri,
        disponibilites: disponibilites.map((plage) => ({
          debut: dateHeure(plage.date, plage.debut),
          fin: dateHeure(plage.date, plage.fin),
        })),
      })
      setRecherche(resultat)
    } catch (error) {
      setErreur(lireErreur(error).message || 'La recherche a échoué. Réessayez.')
      setRecherche(null)
    } finally {
      setChargement(false)
    }
  }

  async function demanderVisite(annonce, creneau) {
    if (!telephone.trim()) {
      setErreur('Renseignez un téléphone de contact avant de demander la visite.')
      return
    }
    setReservationEnCours(annonce.id)
    setErreur('')
    setMessage('')
    try {
      const visite = await creerVisite({
        annonce_id: annonce.id,
        recherche_id: recherche.recherche_id,
        date_visite: creneau.date,
        heure_debut: creneau.heure_debut,
        heure_fin: creneau.heure_fin,
        telephone_contact: telephone.trim(),
        type_visite: 'sur_place',
        nb_personnes: 1,
      })
      setRecherche((avant) => ({
        ...avant,
        items: avant.items.map((item) => item.id === annonce.id
          ? { ...item, creneaux_compatibles: item.creneaux_compatibles.filter((slot) => slot.debut !== creneau.debut) }
          : item).filter((item) => item.creneaux_compatibles.length > 0),
        total: avant.items.filter((item) => item.id !== annonce.id || item.creneaux_compatibles.length > 1).length,
      }))
      setMessage(`Votre demande de visite${visite.reference ? ` ${visite.reference}` : ''} a été envoyée. Le créneau est revalidé par le serveur.`)
    } catch (error) {
      setErreur(lireErreur(error).message || 'Ce créneau vient peut-être d’être réservé. Relancez la recherche.')
    } finally {
      setReservationEnCours(null)
    }
  }

  return (
    <section className="page recherche-visites" aria-labelledby="titre-recherche-visites">
      <h1 id="titre-recherche-visites">Trouver une visite</h1>
      <p className="page__intro">
        Choisissez vos critères et vos disponibilités. Les filtres obligatoires et les créneaux libres sont vérifiés
        avant le classement des annonces.
      </p>

      <form className="recherche-visites__form panneau" onSubmit={lancerRecherche}>
        <fieldset className="recherche-visites__dispos">
          <legend>Mes disponibilités (heure locale)</legend>
          {disponibilites.map((plage, index) => (
            <div className="recherche-visites__dispo" key={`dispo-${index}`}>
              <div className="champ">
                <label htmlFor={`visite-date-${index}`}>Date</label>
                <input id={`visite-date-${index}`} type="date" value={plage.date} required
                  onChange={(event) => modifierDisponibilite(index, 'date', event.target.value)} />
              </div>
              <div className="champ">
                <label htmlFor={`visite-debut-${index}`}>Début</label>
                <input id={`visite-debut-${index}`} type="time" value={plage.debut} required
                  onChange={(event) => modifierDisponibilite(index, 'debut', event.target.value)} />
              </div>
              <div className="champ">
                <label htmlFor={`visite-fin-${index}`}>Fin</label>
                <input id={`visite-fin-${index}`} type="time" value={plage.fin} required
                  onChange={(event) => modifierDisponibilite(index, 'fin', event.target.value)} />
              </div>
              {disponibilites.length > 1 && (
                <button type="button" className="bouton recherche-visites__retirer"
                  aria-label={`Retirer la disponibilité ${index + 1}`}
                  onClick={() => setDisponibilites((avant) => avant.filter((_, i) => i !== index))}>Retirer</button>
              )}
            </div>
          ))}
          <button type="button" className="bouton recherche-visites__ajouter"
            disabled={disponibilites.length >= 10}
            onClick={() => setDisponibilites((avant) => [...avant, disponibiliteVide()])}>Ajouter une disponibilité</button>
          <small>Les créneaux proposés couvrent les 14 prochains jours.</small>
        </fieldset>

        <div className="recherche-visites__criteres">
          <div className="champ">
            <label htmlFor="visite-transaction">Transaction</label>
            <select id="visite-transaction" name="transaction" value={criteres.transaction} onChange={modifierCritere}>
              {Object.entries(LIBELLES_TRANSACTION).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="champ">
            <label htmlFor="visite-type">Type de bien</label>
            <select id="visite-type" name="type_bien" value={criteres.type_bien} onChange={modifierCritere}>
              <option value="">Tous les types</option>
              {Object.entries(LIBELLES_TYPE_BIEN).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="champ">
            <label htmlFor="visite-villes">Ville(s), séparées par des virgules</label>
            <input id="visite-villes" name="villes" value={criteres.villes} onChange={modifierCritere} placeholder="Tunis, Sousse" />
          </div>
          <div className="champ">
            <label htmlFor="visite-budget">Budget maximal (TND)</label>
            <input id="visite-budget" name="budget_max" type="number" min="0" step="0.001" value={criteres.budget_max} onChange={modifierCritere} />
          </div>
          <div className="champ">
            <label htmlFor="visite-pieces">Nombre minimal de pièces</label>
            <input id="visite-pieces" name="pieces_min" type="number" min="0" step="1" value={criteres.pieces_min} onChange={modifierCritere} />
          </div>
          <div className="champ">
            <label htmlFor="visite-tri">Classement</label>
            <select id="visite-tri" name="tri" value={criteres.tri} onChange={modifierCritere}>
              <option value="pertinence">Compatibilité expérimentale</option>
              <option value="chronologique">Plus récentes</option>
            </select>
          </div>
        </div>

        <div className="champ recherche-visites__telephone">
          <label htmlFor="visite-telephone">Téléphone de contact pour la demande</label>
          <input id="visite-telephone" type="tel" value={telephone} onChange={(event) => setTelephone(event.target.value)} autoComplete="tel" />
        </div>
        <button className="bouton bouton--principal recherche-visites__soumettre" type="submit" disabled={chargement}>
          {chargement ? 'Recherche en cours…' : 'Rechercher les visites'}
        </button>
      </form>

      {erreur && <p className="etat etat--erreur" role="alert">{erreur}</p>}
      {message && <p className="etat recherche-visites__confirmation" role="status">{message}</p>}

      {recherche && (
        <section className="recherche-visites__resultats" aria-labelledby="titre-resultats-visites">
          <h2 id="titre-resultats-visites">Annonces avec un créneau compatible</h2>
          <p role="status">{recherche.total} annonce(s) admissible(s).</p>
          <p className="recherche-visites__methode">
            {recherche.tri_applique === 'pertinence'
              ? 'Classement expérimental LightGBM LambdaRank, entraîné sur des données simulées. Son gain sur de vrais visiteurs n’est pas démontré.'
              : recherche.methode_classement === 'chronologique_demande'
                ? 'Tri chronologique demandé.'
                : recherche.message_classement}
          </p>
          {recherche.items.length === 0 ? <p className="etat etat--vide">Aucun autre créneau compatible ne reste affiché. Relancez la recherche pour actualiser les disponibilités.</p> : (
            <div className="recherche-visites__liste">
              {recherche.items.map((annonce, index) => (
                <article className="panneau recherche-visites__annonce" key={annonce.id}>
                  <h3><Link to={`/annonces/${annonce.id}`}>{annonce.titre}</Link></h3>
                  <p>{annonce.ville} · {annonce.surface} m² · {annonce.nb_pieces} pièce(s) · {formaterPrix(annonce.prix, annonce.transaction)}</p>
                  <p className="recherche-visites__rang">
                    Rang {index + 1}{annonce.classement_ia ? ` · score ${annonce.classement_ia.score}` : ''}
                  </p>
                  {annonce.classement_ia?.explications?.length > 0 && (
                    <p className="recherche-visites__explication">Influences positives du modèle : {annonce.classement_ia.explications.map((item) => LIBELLES_INFLUENCES[item.caracteristique] || item.caracteristique).join(', ')}.</p>
                  )}
                  <fieldset className="recherche-visites__slots">
                    <legend>Créneaux disponibles qui correspondent à vos heures</legend>
                    {annonce.creneaux_compatibles.map((creneau) => (
                      <div className="recherche-visites__slot" key={creneau.debut}>
                        <span>{new Date(creneau.debut).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}, {creneau.heure_debut}–{creneau.heure_fin}</span>
                        <button type="button" className="bouton bouton--principal"
                          disabled={reservationEnCours !== null || !telephone.trim()}
                          onClick={() => demanderVisite(annonce, creneau)}>
                          {reservationEnCours === annonce.id ? 'Envoi…' : 'Demander ce créneau'}
                        </button>
                      </div>
                    ))}
                  </fieldset>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </section>
  )
}
