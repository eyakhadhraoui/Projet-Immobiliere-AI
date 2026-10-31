import { useState } from 'react'
import { lireErreur } from '../api/annonces'
import { estimerPrix } from '../api/ia'
import { formaterDate, formaterPrix } from '../utils/format'
import Champ from './Champ'

const CHAMPS_REQUIS = { type_bien: 'type de bien', transaction: 'transaction', ville: 'ville', surface: 'surface', nb_pieces: 'nombre de pièces' }
const SDB_MAX = 20
// Provenance du modèle renvoyée par l'API (IA-ANNONCE-PPT-001) : « demonstration » ou « annonces_reelles ».
const SOURCE_REELLE = 'annonces_reelles'

/**
 * Caractéristiques envoyées à l'estimation, à partir des valeurs du formulaire (ou null s'il en manque).
 * `sdb` : nombre de salles de bain, champ facultatif propre à l'estimation (vide = non envoyé).
 */
function versBien(valeurs, sdb = '') {
  const surface = Number(String(valeurs.surface).replace(',', '.'))
  const pieces = Number(valeurs.nb_pieces)
  const manquants = Object.entries(CHAMPS_REQUIS)
    .filter(([champ]) => {
      if (champ === 'surface') return !(surface > 0)
      if (champ === 'nb_pieces') return valeurs.nb_pieces === '' || !Number.isInteger(pieces) || pieces < 0
      return !String(valeurs[champ] ?? '').trim()
    })
    .map(([, libelle]) => libelle)
  if (manquants.length > 0) return { manquants }
  const salles = String(sdb).trim()
  const nbSdb = Number(salles)
  if (salles !== '' && (!Number.isInteger(nbSdb) || nbSdb < 0 || nbSdb > SDB_MAX)) {
    return { invalide: `Salles de bain : indiquez un nombre entier entre 0 et ${SDB_MAX}, ou laissez le champ vide.` }
  }
  return {
    bien: {
      type_bien: valeurs.type_bien,
      transaction: valeurs.transaction,
      ville: valeurs.ville.trim(),
      surface,
      nb_pieces: pieces,
      meuble: Boolean(valeurs.meuble),
      caracteristiques: [...valeurs.caracteristiques].sort(),
      ...(salles !== '' && { nb_sdb: nbSdb }),
    },
  }
}

/**
 * Bouton « Estimer le prix » du formulaire d'annonce : prix estimé, fourchette, facteurs et avertissement.
 * L'IA propose, le propriétaire décide : le prix n'est repris qu'avec « Utiliser ce prix », et reste modifiable.
 */
export default function EstimationPrix({ valeurs, prixActuel = '', onUtiliserPrix }) {
  const [resultat, setResultat] = useState(null)
  const [estimeSur, setEstimeSur] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [confirmerRemplacement, setConfirmerRemplacement] = useState(false)
  const [sdb, setSdb] = useState('')

  const { bien, manquants, invalide } = versBien(valeurs, sdb)
  const perime = resultat && bien && JSON.stringify(bien) !== estimeSur
  // Confiance renvoyée par l'API (IA-ANNONCE-001-ROBUSTE) : « élevée », « moyenne » ou « faible », avec ses raisons.
  const confiance = resultat?.confiance
  const faible = confiance?.niveau === 'faible'
  const reelle = resultat?.modele?.source === SOURCE_REELLE

  async function estimer() {
    setMessage(null)
    setErreur(null)
    if (manquants) {
      setErreur(`Pour estimer le prix, renseignez d'abord : ${manquants.join(', ')}.`)
      return
    }
    if (invalide) {
      setErreur(invalide)
      return
    }
    setEnCours(true)
    try {
      setResultat(await estimerPrix(bien))
      setEstimeSur(JSON.stringify(bien))
    } catch (error) {
      setResultat(null)
      setErreur(
        error?.response?.status === 503
          ? "L'estimation n'est pas encore disponible : le modèle n'a pas encore été entraîné."
          : lireErreur(error).message,
      )
    } finally {
      setEnCours(false)
    }
  }

  function utiliser() {
    if (perime) return
    if (String(prixActuel).trim() !== '') {
      setConfirmerRemplacement(true)
      return
    }
    confirmerUtilisation()
  }

  function confirmerUtilisation() {
    if (perime) return
    onUtiliserPrix(resultat.prix_estime)
    setConfirmerRemplacement(false)
    setMessage('Prix repris dans le formulaire : vous restez libre de le modifier.')
  }

  const avertissement = resultat && (
    <p className="estimation__avertissement">
      {resultat.avertissement}{' '}
      {reelle
        ? 'Le meublé et les équipements, absents de ces annonces, sont repris des données de démonstration.'
        : 'Modèles de démonstration entraînés sur des données synthétiques, non représentatives de la précision du marché réel.'}
    </p>
  )

  return (
    <section className="formulaire__groupe estimation" aria-labelledby="titre-estimation">
      <div className="estimation__entete">
        <h2 id="titre-estimation" className="estimation__titre">Estimation du prix</h2>
        <button type="button" className="bouton" onClick={estimer} disabled={enCours}>
          {enCours ? 'Estimation en cours…' : resultat ? "Relancer l'estimation" : 'Estimer le prix'}
        </button>
      </div>
      <p className="champ__aide">
        {!resultat
          ? 'Estimation indicative calculée localement, sans service externe. La provenance des données d’entraînement est précisée avec le résultat.'
          : reelle
            ? 'Estimation indicative calculée localement, sans service externe, avec un modèle entraîné sur des annonces immobilières réelles publiées en ligne (prix affichés, pas prix de vente conclus).'
            : 'Estimation indicative calculée localement, sans service externe, avec des modèles entraînés sur des données synthétiques de démonstration. Ces données ne représentent pas le marché réel : le résultat et ses métriques ne permettent pas d’en mesurer la précision sur le marché.'}
      </p>

      <Champ
        nom="nb_sdb"
        libelle="Salles de bain (facultatif)"
        aide="Utilisé seulement pour l’estimation, non enregistré dans l’annonce. Laissé vide, une valeur typique est prise selon le nombre de pièces."
      >
        {(aria) => (
          <input {...aria} type="number" min="0" max={SDB_MAX} step="1" inputMode="numeric" value={sdb} onChange={(e) => setSdb(e.target.value)} />
        )}
      </Champ>

      {erreur && (
        <p className="champ__erreur" role="alert">
          {erreur}
        </p>
      )}

      <div aria-live="polite">
        {resultat && (
          <div className="estimation__resultat">
            {perime && (
              <p className="estimation__perime" role="status">
                Les caractéristiques ont changé depuis l'estimation : relancez-la.
              </p>
            )}
            {/* Confiance faible : l'avertissement passe AVANT le prix, dans un encadré bien visible. */}
            {faible && (
              <div className="estimation__alerte" role="alert">
                <p className="estimation__alerte-titre">Confiance faible</p>
                <ul>
                  {confiance.raisons.map((raison) => (
                    <li key={raison}>{raison}</li>
                  ))}
                </ul>
                {avertissement}
              </div>
            )}
            <p className="estimation__prix">
              Prix estimé : <strong>{formaterPrix(resultat.prix_estime, resultat.transaction)}</strong>
            </p>
            <p className="estimation__fourchette">
              Fourchette probable : {formaterPrix(resultat.fourchette.min, resultat.transaction)} –{' '}
              {formaterPrix(resultat.fourchette.max, resultat.transaction)}
            </p>
            {confiance && !faible && (
              <div className={`estimation__confiance estimation__confiance--${confiance.niveau === 'élevée' ? 'elevee' : 'moyenne'}`}>
                <p>
                  Confiance : <strong>{confiance.niveau}</strong>
                </p>
                <ul>
                  {confiance.raisons.map((raison) => (
                    <li key={raison}>{raison}</li>
                  ))}
                </ul>
              </div>
            )}
            {resultat.facteurs.length > 0 && (
              <>
                <h3 className="estimation__sous-titre">Ce qui influence le plus ce prix</h3>
                <ul className="estimation__facteurs">
                  {resultat.facteurs.map((facteur) => (
                    <li key={facteur.libelle} className={facteur.effet_pourcent >= 0 ? 'facteur facteur--hausse' : 'facteur facteur--baisse'}>
                      <span aria-hidden="true">{facteur.effet_pourcent >= 0 ? '▲' : '▼'}</span> {facteur.libelle} :{' '}
                      <strong>
                        {facteur.effet_pourcent >= 0 ? '+' : ''}
                        {facteur.effet_pourcent} %
                      </strong>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {!faible && avertissement}
            <p className="champ__aide">
              Modèle : {resultat.modele.nom} · erreur moyenne sur les annonces de test : {resultat.modele.mape_test} % ·
              entraîné le {formaterDate(resultat.modele.entraine_le)}
            </p>
            <button type="button" className="bouton bouton--principal" onClick={utiliser} disabled={perime}>
              Utiliser ce prix
            </button>
            {confirmerRemplacement && (
              <div className="estimation__confirmation" role="alertdialog" aria-labelledby="titre-confirmation-prix">
                <p id="titre-confirmation-prix">
                  Le prix saisi ({prixActuel} TND) sera remplacé par l’estimation ({resultat.prix_estime} TND). Confirmer ?
                </p>
                <button type="button" className="bouton bouton--principal" onClick={confirmerUtilisation}>
                  Remplacer le prix
                </button>
                <button type="button" className="bouton" onClick={() => setConfirmerRemplacement(false)}>
                  Garder le prix saisi
                </button>
              </div>
            )}
            {message && (
              <p className="message-succes" role="status">
                {message}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
