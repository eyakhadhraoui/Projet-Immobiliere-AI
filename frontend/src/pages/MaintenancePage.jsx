import { useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { analyserPhotoMaintenance, diagnostiquerMaintenance, locationsActivesMaintenance, listerMaintenance, signalerMaintenance } from '../api/maintenance'
import { useAuth } from '../hooks/useAuth'
import { useRequete } from '../hooks/useRequete'

const CATEGORIES = { plomberie: '🔧 Plomberie', electricite: '⚡ Électricité', climatisation: '❄ Climatisation / chauffage', serrurerie: '🔐 Serrurerie', electromenager: '🔌 Électroménager', autre: 'Autre' }
const PRIORITES = { basse: 'Basse', normale: 'Normale', haute: 'Haute', urgente: 'Urgente' }
const STATUTS = { signalee: 'Signalée', acceptee: 'Acceptée', assignee: 'Assignée', planifiee: 'Planifiée', cloturee: 'Clôturée', refusee: 'Refusée' }
const BADGES = { signalee: 'maintenance-badge--attente', acceptee: 'maintenance-badge--bleu', assignee: 'maintenance-badge--violet', planifiee: 'maintenance-badge--cyan', cloturee: 'maintenance-badge--vert', refusee: 'maintenance-badge--rouge' }
const PIECES = { cuisine: 'Cuisine', salle_de_bain: 'Salle de bain', salon: 'Salon', chambre: 'Chambre', toilettes: 'Toilettes', autre: 'Autre / non identifiée' }
const URGENCES_IA = { faible: 'basse', moyenne: 'normale', elevee: 'haute', critique: 'urgente' }
const PRIORITE_TO_URGENCE = { basse: 'faible', normale: 'moyenne', haute: 'elevee', urgente: 'critique' }
const ORDRE_PRIORITE = { basse: 0, normale: 1, haute: 2, urgente: 3 }

function cartesStats(stats = {}) {
  return <div className="espace-page__stats maintenance__stats">
    <article><span>À traiter</span><strong className="stat--orange">{(stats.signalee || 0) + (stats.acceptee || 0)}</strong></article>
    <article><span>Planifiées</span><strong>{stats.planifiee || 0}</strong></article>
    <article><span>Clôturées</span><strong className="stat--succes">{stats.cloturee || 0}</strong></article>
    <article><span>Coût réel clôturé</span><strong>{(stats.cout_reel || 0).toLocaleString('fr-FR')} TND</strong></article>
  </div>
}

function ListeProprietaire() {
  const [statut, setStatut] = useState('')
  const [priorite, setPriorite] = useState('')
  const [categorie, setCategorie] = useState('')
  const [recherche, setRecherche] = useState('')
  const cle = JSON.stringify({ statut, priorite, categorie, recherche })
  const { donnees, etat, erreur } = useRequete(['maintenance', cle], () => listerMaintenance({ statut, priorite, categorie, recherche }))
  const stats = donnees?.stats || {}
  const items = donnees?.items || []
  return <section className="page espace-page maintenance-page">
    <div className="page__entete espace-page__entete"><div><h1>Maintenance</h1><p className="texte-secondaire">Demandes d’intervention de vos locataires, de la signalisation à la clôture.</p></div><Link className="bouton bouton--secondaire" to="/maintenance/notifications">🔔 Notifications</Link></div>
    {etat === 'succes' && cartesStats(stats)}
    {etat === 'succes' && <>
      <div className="maintenance__onglets">
        {[['', 'Toutes'], ...Object.entries(STATUTS).map(([k, v]) => [k, v])].map(([key, label]) => <button type="button" key={key || 'toutes'} className={statut === key ? 'actif' : ''} onClick={() => setStatut(key)}>{label} · {key ? stats[key] || 0 : donnees.total_global}</button>)}
      </div>
      <div className="filtres-barre maintenance__filtres">
        <input className="champ-saisie" type="search" placeholder="Référence, bien ou locataire" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        <select className="champ-saisie" value={priorite} onChange={(e) => setPriorite(e.target.value)}><option value="">Toutes les priorités</option>{Object.entries(PRIORITES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="champ-saisie" value={categorie} onChange={(e) => setCategorie(e.target.value)}><option value="">Toutes les catégories</option>{Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
    </>}
    {etat === 'chargement' && <p className="etat" role="status">Chargement des demandes…</p>}
    {etat === 'erreur' && <p className="etat etat--erreur" role="alert">{erreur?.message || 'Impossible de charger la maintenance.'}</p>}
    {etat === 'succes' && items.length === 0 && <div className="panneau espace-page__vide"><span className="espace-page__vide-icone">🛠️</span><h2>Aucune demande de maintenance</h2><p>Les signalements de vos locataires apparaîtront ici.</p></div>}
    {etat === 'succes' && items.length > 0 && <div className="maintenance__table-wrap"><table className="maintenance__table"><thead><tr><th>Réf.</th><th>Problème</th><th>Catégorie</th><th>Priorité</th><th>Statut</th><th>Date</th><th> </th></tr></thead><tbody>{items.map((item) => <tr key={item.id}>
      <td>{item.reference}</td><td><strong>{item.titre}</strong><small>{item.annonce_titre} · {item.annonce_ville} · {item.locataire_nom}</small></td><td>{CATEGORIES[item.categorie]}</td><td><span className={`maintenance-badge maintenance-badge--${item.priorite}`}>{PRIORITES[item.priorite]}</span></td><td><span className={`maintenance-badge ${BADGES[item.statut]}`}>{STATUTS[item.statut]}{item.statut === 'cloturee' && item.cout_reel != null ? ` · ${item.cout_reel} TND` : ''}</span></td><td>{new Date(item.date_creation).toLocaleDateString('fr-FR')}</td><td><Link className="bouton bouton--principal bouton--petit" to={`/espace/maintenance/${item.id}`}>Ouvrir</Link></td>
    </tr>)}</tbody></table></div>}
  </section>
}

function FormulaireLocataire() {
  const { utilisateur } = useAuth()
  const [searchParams] = useSearchParams()
  const locationPreselectionnee = searchParams.get('location_id') || ''
  const { donnees: locations, etat: etatLocations } = useRequete('maintenance-locations-actives', locationsActivesMaintenance)
  const { donnees: demandes, etat, reessayer } = useRequete('maintenance-mes-demandes', () => listerMaintenance())
  const [valeurs, setValeurs] = useState({ location_id: locationPreselectionnee, categorie: 'plomberie', piece: 'autre', titre: '', description: '', priorite: 'normale' })
  const [photos, setPhotos] = useState([])
  const champsModifiesRef = useRef(new Set())
  const [analyseEnCours, setAnalyseEnCours] = useState(false)
  const [erreurPhoto, setErreurPhoto] = useState('')
  const [messageAnalyse, setMessageAnalyse] = useState('')
  const [diagnostic, setDiagnostic] = useState(null)
  const [diagnosticEnCours, setDiagnosticEnCours] = useState(false)
  const [erreurDiagnostic, setErreurDiagnostic] = useState('')
  const diagnosticKeyRef = useRef(null)
  const [envoi, setEnvoi] = useState(false)
  const [message, setMessage] = useState('')
  const [erreur, setErreur] = useState('')
  function modifierChamp(champ, valeur) {
    champsModifiesRef.current.add(champ)
    setValeurs((actuelles) => ({ ...actuelles, [champ]: valeur }))
    diagnosticKeyRef.current = null
    setDiagnostic(null)
    setErreurDiagnostic('')
  }
  function selectionnerPhotos(event) {
    const selection = Array.from(event.target.files || []).slice(0, 5)
    const types = new Set(['image/jpeg', 'image/png', 'image/webp'])
    const invalide = selection.find((fichier) => !types.has(fichier.type) || fichier.size >= 10 * 1024 * 1024)
    if (invalide) {
      setPhotos([])
      setErreurPhoto(!types.has(invalide.type) ? 'Format accepté : JPEG, PNG ou WebP.' : 'Chaque photo doit faire moins de 10 Mo.')
      event.target.value = ''
      return
    }
    setPhotos(selection)
    setErreurPhoto('')
    setMessageAnalyse('')
  }
  async function analyserPhoto() {
    const photo = photos[0]
    if (!photo) { setErreurPhoto('Choisissez une photo avant de lancer l’analyse.'); return }
    if (!valeurs.location_id) { setErreurPhoto('Choisissez d’abord le contrat de location concerné.'); return }
    setAnalyseEnCours(true); setErreurPhoto(''); setMessageAnalyse('')
    diagnosticKeyRef.current = null; setDiagnostic(null)
    try {
      const suggestion = await analyserPhotoMaintenance(photo, valeurs.location_id)
      if (!suggestion.is_maintenance_issue) {
        setMessageAnalyse('La photo ne semble pas montrer un incident de maintenance. Vérifiez-la ou remplissez le formulaire manuellement.')
        return
      }
      const propositions = { piece: suggestion.room, titre: suggestion.title, description: suggestion.description, priorite: URGENCES_IA[suggestion.urgency] }
      setValeurs((actuelles) => {
        const suivantes = { ...actuelles }
        for (const [champ, valeur] of Object.entries(propositions)) {
          if (valeur && !champsModifiesRef.current.has(champ)) suivantes[champ] = valeur
        }
        return suivantes
      })
      const confiance = Number.isFinite(suggestion.confidence) ? ` (confiance estimée : ${Math.round(suggestion.confidence * 100)} %)` : ''
      setMessageAnalyse(`Suggestions appliquées uniquement aux champs non modifiés${confiance}. Vérifiez-les avant l’envoi.`)
    } catch (error) {
      setErreurPhoto(
        error.response?.data?.message ||
          error.response?.data?.error ||
          error.response?.data?.errors?.photo ||
          'L’analyse de la photo a échoué. Réessayez.',
      )
    } finally { setAnalyseEnCours(false) }
  }
  async function obtenirDiagnostic() {
    const donnees = {
      location_id: Number(valeurs.location_id),
      category: valeurs.categorie,
      room: valeurs.piece,
      urgency: PRIORITE_TO_URGENCE[valeurs.priorite],
      title: valeurs.titre.trim(),
      description: valeurs.description.trim(),
    }
    if (!donnees.location_id || donnees.title.length < 5 || donnees.description.length < 10) {
      setErreurDiagnostic('Choisissez un bail actif et saisissez un titre et une description suffisamment détaillés.')
      return
    }
    const key = JSON.stringify(donnees)
    diagnosticKeyRef.current = key
    setDiagnostic(null); setErreurDiagnostic(''); setDiagnosticEnCours(true)
    try {
      const resultat = await diagnostiquerMaintenance(donnees)
      if (diagnosticKeyRef.current === key) setDiagnostic(resultat)
    } catch (error) {
      if (diagnosticKeyRef.current === key) setErreurDiagnostic(error.response?.data?.error || error.response?.data?.message || 'Le diagnostic est indisponible. Réessayez plus tard.')
    } finally { setDiagnosticEnCours(false) }
  }
  const urgenceProposee = diagnostic ? URGENCES_IA[diagnostic.urgence_recommandee] : null
  const escaladeUrgence = urgenceProposee && ORDRE_PRIORITE[urgenceProposee] > ORDRE_PRIORITE[valeurs.priorite]
  async function soumettre(event) {
    event.preventDefault(); setEnvoi(true); setErreur(''); setMessage('')
    try {
      const item = await signalerMaintenance(valeurs, photos)
      setValeurs((v) => ({ ...v, titre: '', description: '', piece: 'autre', priorite: 'normale' })); setPhotos([]); champsModifiesRef.current.clear(); setMessageAnalyse('')
      setMessage(`Signalement ${item.reference} envoyé au propriétaire.`); reessayer()
    } catch (error) { setErreur(error.response?.data?.message || 'Impossible d’envoyer le signalement.') }
    finally { setEnvoi(false) }
  }
  return <section className="page maintenance-page maintenance-page--locataire">
    <header className="maintenance__intro"><div><h1>Signaler un problème</h1><p>{utilisateur?.role === 'proprietaire' ? 'Le signalement sera associé au bail et ajouté à son historique.' : 'Votre propriétaire sera notifié immédiatement.'}</p></div><Link to="/maintenance/notifications">🔔 Notifications</Link></header>
    {message && <p className="message-succes" role="status">{message}</p>}{erreur && <p className="etat etat--erreur" role="alert">{erreur}</p>}
    <form className="maintenance-form panneau" onSubmit={soumettre}>
      <label>Bien concerné<select required value={valeurs.location_id} onChange={(e) => modifierChamp('location_id', e.target.value)}><option value="">Choisir un contrat actif</option>{(locations || []).map((loc) => <option key={loc.id} value={loc.id}>{loc.titre} · {loc.ville} · bail actif</option>)}</select></label>
      <small>Seuls les biens avec un contrat de location actif sont proposés.</small>
      {etatLocations === 'succes' && !locations?.length && <p role="status">Aucun bail actif n’est associé à votre compte.</p>}
      <fieldset><legend>Catégorie</legend><div className="maintenance__choix">{Object.entries(CATEGORIES).map(([key, label]) => <label key={key} className={valeurs.categorie === key ? 'selectionne' : ''}><input type="radio" name="categorie" value={key} checked={valeurs.categorie === key} onChange={() => modifierChamp('categorie', key)} />{label}</label>)}</div></fieldset>
      <label>Pièce concernée<select value={valeurs.piece} onChange={(e) => modifierChamp('piece', e.target.value)}>{Object.entries(PIECES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Titre<input required maxLength={160} value={valeurs.titre} onChange={(e) => modifierChamp('titre', e.target.value)} placeholder="Ex. Fuite sous l’évier" /></label>
      <label>Description<textarea required maxLength={5000} rows={4} value={valeurs.description} onChange={(e) => modifierChamp('description', e.target.value)} placeholder="Décrivez le problème et les actions déjà tentées." /></label>
      <label>Photos (jusqu’à 5)<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={selectionnerPhotos} /><small>{photos.map((f) => f.name).join(' · ') || 'JPG, PNG ou WebP — moins de 10 Mo par photo'}</small></label>
      {photos.length > 0 && <div className="maintenance-form__actions"><button type="button" className="bouton bouton--secondaire" disabled={analyseEnCours || !valeurs.location_id} onClick={analyserPhoto}>{analyseEnCours ? 'Analyse Gemini en cours…' : 'Analyser la photo avec l’IA'}</button></div>}
      {photos.length > 0 && <small>La première photo sélectionnée sera envoyée à Google Gemini pour l’analyse.</small>}
      {erreurPhoto && <p className="etat etat--erreur" role="alert">{erreurPhoto}</p>}{messageAnalyse && <p className="message-succes" role="status">{messageAnalyse}</p>}
      <fieldset><legend>Priorité</legend><div className="maintenance__choix">{Object.entries(PRIORITES).map(([key, label]) => <label key={key} className={valeurs.priorite === key ? `selectionne priorite-${key}` : ''}><input type="radio" name="priorite" value={key} checked={valeurs.priorite === key} onChange={() => modifierChamp('priorite', key)} />{label}</label>)}</div></fieldset>
      <section className="maintenance-diagnostic" aria-live="polite">
        <div className="maintenance-form__actions"><button type="button" className="bouton bouton--secondaire" disabled={diagnosticEnCours || !valeurs.location_id || valeurs.titre.trim().length < 5 || valeurs.description.trim().length < 10} onClick={obtenirDiagnostic}>{diagnosticEnCours ? 'Recherche et diagnostic en cours…' : 'Obtenir un diagnostic du guide'}</button></div>
        <small>Le diagnostic utilise les trois fiches les plus proches du guide et ne remplace pas l’avis d’un professionnel.</small>
        <small>Le titre et la description sont envoyés à Gemini pour le diagnostic ; ils ne sont pas conservés côté fournisseur.</small>
        {erreurDiagnostic && <p className="etat etat--erreur" role="alert">{erreurDiagnostic}</p>}
        {diagnostic && <article className="maintenance-diagnostic__resultat">
          <h3>Diagnostic proposé par le guide</h3>
          {diagnostic.fiche_id === 'AUCUNE' ? <p>Le guide ne contient pas de fiche suffisamment adaptée. Faites vérifier le problème par un technicien.</p> : <p><strong>Fiche retenue :</strong> {diagnostic.fiche_titre || diagnostic.fiche_id}</p>}
          {diagnostic.correspondance_faible && <p className="maintenance-diagnostic__avertissement">La correspondance avec le guide est faible. Vérifiez attentivement les conseils proposés.</p>}
          <p><strong>Cause probable :</strong> {diagnostic.cause_probable}</p>
          <p><strong>Diagnostic :</strong> {diagnostic.diagnostic}</p>
          <h4>Actions immédiates</h4>
          {diagnostic.actions_immediates?.length ? <ul>{diagnostic.actions_immediates.map((action, index) => <li key={`${index}-${action}`}>{action}</li>)}</ul> : <p>Aucune action sûre à proposer à partir du guide.</p>}
          <p><strong>Urgence recommandée :</strong> {PRIORITES[urgenceProposee]} — {diagnostic.justification_urgence}</p>
          {escaladeUrgence && <div className="maintenance-diagnostic__escalade" role="alert"><span>L’urgence suggérée est supérieure à celle sélectionnée.</span><button type="button" className="bouton bouton--principal bouton--petit" onClick={() => { champsModifiesRef.current.add('priorite'); setValeurs((actuelles) => ({ ...actuelles, priorite: urgenceProposee })); diagnosticKeyRef.current = null }}>Appliquer « {PRIORITES[urgenceProposee]} »</button></div>}
          {diagnostic.estimation && <div className="maintenance-diagnostic__estimation"><strong>Estimation indicative</strong><p>Coût : {diagnostic.estimation.cout_min}–{diagnostic.estimation.cout_max} {diagnostic.estimation.devise} · Durée : {diagnostic.estimation.duree_libelle}</p><p>{diagnostic.estimation.technicien} · Fiabilité : {diagnostic.estimation.fiabilite}</p><small>{diagnostic.estimation.avertissement}</small></div>}
          {diagnostic.estimation?.facteurs_de_variation && <p><strong>Facteurs de variation :</strong> {diagnostic.estimation.facteurs_de_variation}</p>}
        </article>}
      </section>
      <div className="maintenance-form__actions"><button className="bouton bouton--principal" disabled={envoi || !locations?.length}>{envoi ? 'Envoi…' : 'Envoyer le signalement'}</button></div>
    </form>
    <section className="maintenance__mes-demandes"><h2>Mes signalements</h2>{etat === 'succes' && (demandes?.items || []).map((item) => <Link key={item.id} to={`/maintenance/${item.id}`}><strong>{item.titre}</strong><span>{item.reference} · {item.annonce_titre}</span><b className={`maintenance-badge ${BADGES[item.statut]}`}>{STATUTS[item.statut]}</b></Link>)}</section>
  </section>
}

export default function MaintenancePage() {
  const { utilisateur } = useAuth()
  const [searchParams] = useSearchParams()
  const signalementDepuisLocation = Boolean(searchParams.get('location_id'))
  return utilisateur?.role === 'proprietaire' && !signalementDepuisLocation ? <ListeProprietaire /> : <FormulaireLocataire key={searchParams.get('location_id') || 'sans-location'} />
}
