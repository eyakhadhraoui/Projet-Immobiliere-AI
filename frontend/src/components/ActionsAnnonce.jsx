import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { lireErreur, obtenirCreneauxVisite } from '../api/annonces'
import { creerVisite } from '../api/visites'
import { creerTransaction } from '../api/transactions'
import { creerLocation } from '../api/locations'
import { useAuth } from '../hooks/useAuth'
import { formaterPrix } from '../utils/format'

const maintenant = () => new Date().toISOString().slice(0, 10)

function creerFormulaire(action, annonce, utilisateur) {
  if (action === 'visite') return {
    annonce_id: annonce.id,
    client_id: utilisateur?.id ? String(utilisateur.id) : '',
    date_visite: '',
    heure_debut: '',
    heure_fin: '',
    type_visite: 'sur_place',
    nb_personnes: 1,
    telephone_contact: utilisateur?.telephone || '',
    message_client: '',
  }
  if (action === 'location') return {
    annonce_id: annonce.id,
    locataire_id: utilisateur?.id ? String(utilisateur.id) : '',
    type_location: 'longue_duree',
    date_debut: maintenant(),
    date_fin: '',
    duree_mois: 12,
    loyer_mensuel: annonce.prix || '',
    charges: 0,
    caution: (annonce.prix || 0) * 2,
    jour_paiement: 5,
    periodicite: 'mensuel',
    renouvellement_auto: true,
    preavis_jours: 90,
  }
  return {
    annonce_id: annonce.id,
    acheteur_id: utilisateur?.id ? String(utilisateur.id) : '',
    type_transaction: annonce.transaction === 'location' ? 'location' : 'vente',
    montant_total: annonce.prix || '',
    acompte: 0,
    mode_paiement: 'virement',
    date_signature: '',
    notaire: '',
    reference_acte: '',
    observations: '',
  }
}

const configActions = {
  visite: { titre: 'Demander une visite', classe: 'actions-annonce__entete--visite', envoyer: creerVisite, bouton: 'Envoyer la demande' },
  location: { titre: 'Nouveau contrat de location', classe: 'actions-annonce__entete--location', envoyer: creerLocation, bouton: 'Créer le contrat' },
  transaction: { titre: 'Nouvelle transaction', classe: 'actions-annonce__entete--transaction', envoyer: creerTransaction, bouton: 'Créer la transaction' },
}

function Champ({ label, nom, valeur, changer, type = 'text', requis = false, children, ...props }) {
  return (
    <div className="actions-annonce__champ">
      <label htmlFor={`action-${nom}`}>{label}{requis ? ' *' : ''}</label>
      {children || <input id={`action-${nom}`} name={nom} type={type} value={valeur ?? ''} onChange={changer} required={requis} {...props} />}
    </div>
  )
}

function PartieConnectee({ action, utilisateur }) {
  const nom = action === 'visite' ? 'client_id' : action === 'location' ? 'locataire_id' : 'acheteur_id'
  const label = action === 'visite' ? 'Visiteur' : action === 'location' ? 'Locataire' : 'Acheteur'
  const nomComplet = [utilisateur?.prenom, utilisateur?.nom].filter(Boolean).join(' ')
  return <>
    <div className="actions-annonce__champ">
      <label htmlFor={`action-${nom}`}>{label} *</label>
      <input id={`action-${nom}`} value={nomComplet || utilisateur?.email || 'Compte connecté'} readOnly />
      <small>Le compte actuellement connecté sera associé à cette opération.</small>
    </div>
  </>
}

function VisiteurConnecte({ utilisateur }) {
  const nom = [utilisateur?.prenom, utilisateur?.nom].filter(Boolean).join(' ')
  return (
    <div className="actions-annonce__champ">
      <label htmlFor="action-visiteur-connecte">Visiteur *</label>
      <input id="action-visiteur-connecte" value={nom || utilisateur?.email || 'Compte connecté'} readOnly />
    </div>
  )
}

function ChampsVisite({ form, changer, creneaux, chargementCreneaux, selectionnerCreneau }) {
  return <>
    <div className="actions-annonce__champ actions-annonce__champ--large">
      <span className="actions-annonce__libelle">Créneaux compatibles pour votre visite *</span>
      <p className="actions-annonce__aide">
        Les propositions respectent les disponibilités du bien. Leur score indique leur compatibilité avec l’horaire et l’organisation des visites.
      </p>
      {chargementCreneaux && <p className="actions-annonce__aide">Recherche des meilleurs créneaux…</p>}
      {!chargementCreneaux && creneaux.length === 0 && (
        <p className="actions-annonce__aide actions-annonce__aide--erreur">
          Aucun créneau n'est disponible pour cette annonce.
        </p>
      )}
      <div className="creneaux-visite" role="list" aria-label="Créneaux de visite proposés">
        {creneaux.map((creneau) => {
          const choisi = form.date_visite === creneau.date && form.heure_debut === creneau.heure_debut
          return (
            <button
              type="button"
              role="listitem"
              className={`creneau-visite${choisi ? ' creneau-visite--choisi' : ''}`}
              key={`${creneau.debut}-${creneau.fin}`}
              onClick={() => selectionnerCreneau(creneau)}
            >
              <strong>{creneau.etiquette}</strong>
              <span>{new Date(creneau.debut).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
              <span>{creneau.heure_debut} - {creneau.heure_fin}</span>
              <span>Compatibilité : {creneau.score}/100</span>
              <small>{creneau.raisons.join(' · ')}</small>
            </button>
          )
        })}
      </div>
    </div>
    <Champ label="Type de visite" nom="type_visite" valeur={form.type_visite} changer={changer} requis>
      <select id="action-type_visite" name="type_visite" value={form.type_visite} onChange={changer}>
        <option value="sur_place">Sur place</option><option value="virtuelle">Virtuelle</option>
      </select>
    </Champ>
    <Champ label="Nombre de personnes" nom="nb_personnes" type="number" valeur={form.nb_personnes} changer={changer} min="1" max="10" />
    <Champ label="Téléphone de contact" nom="telephone_contact" type="tel" valeur={form.telephone_contact} changer={changer} requis />
    <div className="actions-annonce__champ actions-annonce__champ--large">
      <label htmlFor="action-message_client">Message au propriétaire</label>
      <textarea id="action-message_client" name="message_client" rows="3" value={form.message_client} onChange={changer} />
    </div>
  </>
}

function ChampsLocation({ form, changer, action, utilisateur }) {
  return <>
    <PartieConnectee action={action} utilisateur={utilisateur} />
    <Champ label="Type de location" nom="type_location" valeur={form.type_location} changer={changer}>
      <select id="action-type_location" name="type_location" value={form.type_location} onChange={changer}>
        <option value="longue_duree">Longue durée</option><option value="saisonniere">Saisonnière</option><option value="meublee">Meublée</option><option value="commerciale">Commerciale</option>
      </select>
    </Champ>
    <Champ label="Date de début" nom="date_debut" type="date" valeur={form.date_debut} changer={changer} requis />
    <Champ label="Date de fin" nom="date_fin" type="date" valeur={form.date_fin} changer={changer} />
    <Champ label="Loyer mensuel (TND)" nom="loyer_mensuel" type="number" valeur={form.loyer_mensuel} changer={changer} step="0.001" requis />
    <Champ label="Charges (TND)" nom="charges" type="number" valeur={form.charges} changer={changer} step="0.001" />
    <Champ label="Caution (TND)" nom="caution" type="number" valeur={form.caution} changer={changer} step="0.001" />
    <Champ label="Jour de paiement" nom="jour_paiement" type="number" valeur={form.jour_paiement} changer={changer} min="1" max="28" />
    <Champ label="Périodicité" nom="periodicite" valeur={form.periodicite} changer={changer}>
      <select id="action-periodicite" name="periodicite" value={form.periodicite} onChange={changer}>
        <option value="mensuel">Mensuelle</option><option value="trimestriel">Trimestrielle</option><option value="annuel">Annuelle</option>
      </select>
    </Champ>
    <Champ label="Préavis (jours)" nom="preavis_jours" type="number" valeur={form.preavis_jours} changer={changer} min="0" />
    <Champ label="Renouvellement automatique" nom="renouvellement_auto" valeur={form.renouvellement_auto ? 'oui' : 'non'} changer={(event) => changer({ target: { name: 'renouvellement_auto', value: event.target.value === 'oui' } })}>
      <select id="action-renouvellement_auto" name="renouvellement_auto" value={form.renouvellement_auto ? 'oui' : 'non'} onChange={(event) => changer({ target: { name: 'renouvellement_auto', value: event.target.value === 'oui' } })}>
        <option value="oui">Oui</option><option value="non">Non</option>
      </select>
    </Champ>
    <Champ label="Durée (mois)" nom="duree_mois" type="number" valeur={form.duree_mois} changer={changer} min="1" max="120" />
  </>
}

function ChampsTransaction({ form, changer, action, utilisateur }) {
  return <>
    <Champ label="Type de transaction" nom="type_transaction" valeur={form.type_transaction} changer={changer}>
      <select id="action-type_transaction" name="type_transaction" value={form.type_transaction} onChange={changer}>
        <option value="vente">Vente</option><option value="location">Location</option><option value="reservation">Réservation</option>
      </select>
    </Champ>
    <PartieConnectee action={action} utilisateur={utilisateur} />
    <Champ label="Montant total (TND)" nom="montant_total" type="number" valeur={form.montant_total} changer={changer} step="0.001" requis />
    <Champ label="Acompte (TND)" nom="acompte" type="number" valeur={form.acompte} changer={changer} step="0.001" />
    <Champ label="Mode de paiement" nom="mode_paiement" valeur={form.mode_paiement} changer={changer}>
      <select id="action-mode_paiement" name="mode_paiement" value={form.mode_paiement} onChange={changer}>
        <option value="virement">Virement</option><option value="cheque">Chèque</option><option value="especes">Espèces</option><option value="carte">Carte</option><option value="flouci">Flouci</option><option value="paymee">Paymee</option>
      </select>
    </Champ>
    <Champ label="Date de signature" nom="date_signature" type="date" valeur={form.date_signature} changer={changer} />
    <Champ label="Notaire" nom="notaire" valeur={form.notaire} changer={changer} />
    <Champ label="Référence de l’acte" nom="reference_acte" valeur={form.reference_acte} changer={changer} />
    <div className="actions-annonce__champ actions-annonce__champ--large">
      <label htmlFor="action-observations">Observations</label>
      <textarea id="action-observations" name="observations" rows="3" value={form.observations} onChange={changer} />
    </div>
  </>
}

/** Fenêtre de saisie rapide ouverte depuis une carte d’annonce. */
export default function ActionsAnnonce({ annonce, action, fermer, termine }) {
  const { utilisateur } = useAuth()
  const configuration = configActions[action]
  const [form, setForm] = useState(() => creerFormulaire(action, annonce, utilisateur))
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [creneaux, setCreneaux] = useState([])
  const [chargementCreneaux, setChargementCreneaux] = useState(action === 'visite')

  useEffect(() => {
    if (action !== 'visite') return undefined
    let active = true
    obtenirCreneauxVisite(annonce.id)
      .then((resultat) => { if (active) setCreneaux(resultat.creneaux || []) })
      .catch((error) => { if (active) setErreur(lireErreur(error).message) })
      .finally(() => { if (active) setChargementCreneaux(false) })
    return () => { active = false }
  }, [action, annonce.id])

  useEffect(() => {
    const touche = (event) => { if (event.key === 'Escape') fermer() }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
  }, [fermer])

  function changer(event) {
    setForm((precedent) => ({ ...precedent, [event.target.name]: event.target.value }))
  }

  function selectionnerCreneau(creneau) {
    setForm((precedent) => ({
      ...precedent,
      date_visite: creneau.date,
      heure_debut: creneau.heure_debut,
      heure_fin: creneau.heure_fin,
    }))
  }

  async function soumettre(event) {
    event.preventDefault()
    setChargement(true)
    setErreur('')
    try {
      if (action !== 'visite' && !utilisateur?.id) {
        setErreur('Connectez-vous pour associer votre compte à ce contrat ou à cette transaction.')
        return
      }
      const donnees = Object.fromEntries(Object.entries(form).map(([cle, valeur]) => [cle, ['annonce_id', 'client_id', 'locataire_id', 'acheteur_id', 'nb_personnes', 'jour_paiement', 'duree_mois', 'preavis_jours'].includes(cle) && valeur !== '' ? Number(valeur) : valeur]))
      await configuration.envoyer(donnees)
      termine(action)
    } catch (error) {
      setErreur(lireErreur(error).message)
    } finally {
      setChargement(false)
    }
  }

  const classes = `actions-annonce__dialogue${action === 'visite' ? ' actions-annonce__dialogue--visite' : ''}`
  return createPortal(
    <div className="actions-annonce__voile" onMouseDown={(event) => event.target === event.currentTarget && fermer()}>
      <section className={classes} role="dialog" aria-modal="true" aria-labelledby="action-annonce-titre">
        <header className={`actions-annonce__entete ${configuration.classe}`}>
          <div>
            <h2 id="action-annonce-titre">{configuration.titre}</h2>
            <p>{annonce.titre} · {annonce.ville} · {formaterPrix(annonce.prix, annonce.transaction)}</p>
          </div>
          <button type="button" onClick={fermer} aria-label="Fermer">×</button>
        </header>
        <form onSubmit={soumettre}>
          <div className="actions-annonce__grille">
            <div className="actions-annonce__champ actions-annonce__champ--large">
              <label>Annonce</label>
              <input value={annonce.titre} readOnly />
            </div>
            {action === 'visite' && <VisiteurConnecte utilisateur={utilisateur} />}
            {action === 'visite' && (
              <ChampsVisite
                form={form}
                changer={changer}
                creneaux={creneaux}
                chargementCreneaux={chargementCreneaux}
                selectionnerCreneau={selectionnerCreneau}
              />
            )}
            {action === 'location' && <ChampsLocation form={form} changer={changer} action={action} utilisateur={utilisateur} />}
            {action === 'transaction' && <ChampsTransaction form={form} changer={changer} action={action} utilisateur={utilisateur} />}
          </div>
          {erreur && <p className="actions-annonce__erreur" role="alert">{erreur}</p>}
          <footer className="actions-annonce__pied">
            <button type="button" className="bouton" onClick={fermer}>Annuler</button>
            <button
              type="submit"
              className="bouton bouton--principal"
              disabled={chargement || (action === 'visite' && (chargementCreneaux || !form.date_visite))}
            >
              {chargement ? 'Enregistrement…' : configuration.bouton}
            </button>
          </footer>
        </form>
      </section>
    </div>,
    document.body,
  )
}
