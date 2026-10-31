import { useEffect, useMemo, useRef, useState } from 'react'
import { ajouterMessageReclamation, ameliorerDescriptionReclamation, analyserAssistantReclamation, creerReclamation, listerReclamations, modifierReclamation, supprimerReclamation } from '../../api/reclamations'
import { lireErreur, listerAnnonces } from '../../api/annonces'
import ModalConfirmation from '../../components/ModalConfirmation'
import MessageErreur from '../../components/MessageErreur'
import { useRequete } from '../../hooks/useRequete'
import { formaterDateHeure } from '../../utils/format'

const STATUTS = {
  nouvelle: 'Nouvelle',
  en_cours: 'En cours',
  en_attente_info: 'En attente info',
  resolue: 'Résolue',
  rejetee: 'Rejetée',
  cloturee: 'Clôturée',
}

const TYPES = {
  fausse_annonce: 'Fausse annonce',
  prix_incorrect: 'Prix incorrect',
  photos_trompeuses: 'Photos trompeuses',
  bien_deja_loue_vendu: 'Déjà loué / vendu',
  comportement_proprietaire: 'Comportement',
  contenu_inapproprie: 'Contenu inapproprié',
  probleme_technique: 'Problème technique',
  autre: 'Autre',
}

const PRIORITES = { basse: 'Basse', normale: 'Normale', haute: 'Haute', urgente: 'Urgente' }
const AUCUNE_RECLAMATION = []

const classeStatut = (statut) =>
  ({
    nouvelle: 'reclamation__badge--nouvelle',
    en_cours: 'reclamation__badge--cours',
    en_attente_info: 'reclamation__badge--attente',
    resolue: 'reclamation__badge--resolue',
    rejetee: 'reclamation__badge--fermee',
    cloturee: 'reclamation__badge--fermee',
  })[statut] || ''

const classePriorite = (priorite) =>
  ({
    basse: 'reclamation__badge--basse',
    normale: 'reclamation__badge--normale',
    haute: 'reclamation__badge--haute',
    urgente: 'reclamation__badge--urgente',
  })[priorite] || ''

const classeType = (type) => ({
  fausse_annonce: 'reclamation__type--annonce', prix_incorrect: 'reclamation__type--prix',
  photos_trompeuses: 'reclamation__type--photos', bien_deja_loue_vendu: 'reclamation__type--disponibilite',
  comportement_proprietaire: 'reclamation__type--comportement', contenu_inapproprie: 'reclamation__type--contenu',
  probleme_technique: 'reclamation__type--technique', autre: 'reclamation__type--autre',
})[type] || ''

function NouvelleReclamation({ fermer, creee }) {
  const [annonces, setAnnonces] = useState([])
  const [form, setForm] = useState({ annonce_id: '', type: 'fausse_annonce', objet: '', description: '', priorite: 'normale' })
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [fichiers, setFichiers] = useState([])
  const [assistant, setAssistant] = useState(null)
  const [assistantEnCours, setAssistantEnCours] = useState(false)
  const [assistantErreur, setAssistantErreur] = useState('')
  const [descriptionProposee, setDescriptionProposee] = useState('')
  const [ameliorationEnCours, setAmeliorationEnCours] = useState(false)
  const [erreurAmelioration, setErreurAmelioration] = useState('')
  const requeteAmelioration = useRef(0)
  const [erreurFichier, setErreurFichier] = useState('')
  const descriptionMax = 1000
  function changerChamp(champ, valeur) {
    if (champ === 'objet' || champ === 'description' || champ === 'annonce_id') {
      setAssistant(null)
      if (champ === 'objet' || champ === 'description') {
        requeteAmelioration.current += 1
        setDescriptionProposee('')
        setErreurAmelioration('')
        setAmeliorationEnCours(false)
      }
    }
    setForm((precedent) => ({ ...precedent, [champ]: valeur }))
  }

  useEffect(() => {
    let actif = true
    listerAnnonces({ statut: 'publiee', page: 1, per_page: 50 })
      .then((resultat) => { if (actif) setAnnonces(resultat.items || []) })
      .catch(() => {})
    return () => { actif = false }
  }, [])

  useEffect(() => {
    if (!form.objet && !form.description) return undefined
    let actif = true
    const minuteur = window.setTimeout(async () => {
      setAssistantEnCours(true)
      setAssistantErreur('')
      try {
        const resultat = await analyserAssistantReclamation({ ...form, annonce_id: form.annonce_id || null })
        if (actif) setAssistant(resultat)
      } catch (error) {
        if (actif) {
          setAssistant(null)
          setAssistantErreur(lireErreur(error).message || 'Gemini ne peut pas analyser le texte pour le moment.')
        }
      }
      finally { if (actif) setAssistantEnCours(false) }
    }, 1200)
    return () => { actif = false; window.clearTimeout(minuteur) }
  }, [form])

  async function demanderAmeliorationDescription() {
    const objet = form.objet.trim()
    const description = form.description.trim()
    if (!objet && !description) {
      setErreurAmelioration('Saisissez un objet ou quelques faits avant de demander une proposition.')
      return
    }
    const idRequete = ++requeteAmelioration.current
    setAmeliorationEnCours(true)
    setErreurAmelioration('')
    setDescriptionProposee('')
    try {
      const resultat = await ameliorerDescriptionReclamation({ objet, description })
      if (requeteAmelioration.current === idRequete) setDescriptionProposee(resultat.description || '')
    } catch (error) {
      if (requeteAmelioration.current === idRequete) {
        setErreurAmelioration(lireErreur(error).message || 'Gemini ne peut pas proposer une reformulation pour le moment.')
      }
    } finally {
      if (requeteAmelioration.current === idRequete) setAmeliorationEnCours(false)
    }
  }

  function ajouterFichiers(selection) {
    setErreurFichier('')
    const ajoutes = Array.from(selection || [])
    const valides = ajoutes.filter((fichier) => /\.(jpe?g|png|pdf)$/i.test(fichier.name) && fichier.size > 0 && fichier.size <= 5 * 1024 * 1024)
    if (valides.length !== ajoutes.length) setErreurFichier('Formats acceptés : JPG, PNG ou PDF. Chaque fichier doit faire au plus 5 Mo.')
    const combine = [...fichiers, ...valides]
    if (combine.reduce((somme, fichier) => somme + fichier.size, 0) > 5 * 1024 * 1024) {
      setErreurFichier('La taille totale des pièces jointes ne peut pas dépasser 5 Mo.')
      return
    }
    setFichiers(combine)
  }

  async function envoyer(event) {
    event.preventDefault()
    setChargement(true)
    setErreur('')
    try {
      const donnees = { ...form, annonce_id: form.annonce_id ? Number(form.annonce_id) : null }
      creee(await creerReclamation(donnees, fichiers))
    } catch (error) {
      setErreur(lireErreur(error).message)
    } finally {
      setChargement(false)
    }
  }

  return (
    <div className="reclamation__voile" onMouseDown={(event) => event.target === event.currentTarget && fermer()}>
      <section className="reclamation__dialogue reclamation__dialogue--nouveau" role="dialog" aria-modal="true" aria-labelledby="nouvelle-reclamation-titre">
        <header className="reclamation__dialogue-entete">
          <h2 id="nouvelle-reclamation-titre">Nouvelle réclamation</h2>
          <button type="button" className="reclamation__fermer" onClick={fermer} aria-label="Fermer">×</button>
        </header>
        <form className="reclamation__dialogue-corps reclamation__formulaire" onSubmit={envoyer}>
          <div className="reclamation__form-colonne">
          <label htmlFor="reclamation-annonce">Annonce concernée</label>
          <select id="reclamation-annonce" value={form.annonce_id} onChange={(event) => changerChamp('annonce_id', event.target.value)}>
            <option value="">Aucune annonce précise</option>
            {annonces.map((annonce) => <option value={annonce.id} key={annonce.id}>{annonce.titre}</option>)}
          </select>
          <label htmlFor="reclamation-type">Motif</label>
          <select id="reclamation-type" value={form.type} onChange={(event) => changerChamp('type', event.target.value)}>
            {Object.entries(TYPES).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <label htmlFor="reclamation-objet">Objet</label>
          <input id="reclamation-objet" value={form.objet} onChange={(event) => changerChamp('objet', event.target.value)} maxLength="150" required />
          <label htmlFor="reclamation-description">Description</label>
          <textarea id="reclamation-description" rows="5" value={form.description} maxLength={descriptionMax} onChange={(event) => changerChamp('description', event.target.value)} required />
          <div className="reclamation__description-actions">
            <button type="button" className="bouton bouton--assistant" disabled={ameliorationEnCours || chargement || (!form.objet.trim() && !form.description.trim())} onClick={demanderAmeliorationDescription}>
              {ameliorationEnCours ? 'Gemini prépare une proposition…' : form.description.trim() ? 'Améliorer la description avec Gemini' : 'Générer une description avec Gemini'}
            </button>
          </div>
          {erreurAmelioration && <p role="alert" className="reclamation__erreur">{erreurAmelioration}</p>}
          {descriptionProposee && <section className="reclamation__description-proposee" aria-label="Proposition de description à relire">
            <h4>Proposition Gemini à relire</h4>
            <p>{descriptionProposee}</p>
            <button type="button" className="bouton bouton--secondaire" onClick={() => changerChamp('description', descriptionProposee)}>Utiliser cette proposition</button>
          </section>}
          <div className="reclamation__compteur" aria-live="polite">{form.description.length} / {descriptionMax} caractères</div>
          <label htmlFor="reclamation-pieces">Pièces jointes (captures, messages)</label>
          <div className="reclamation__depot">
            <input id="reclamation-pieces" type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" multiple onChange={(event) => { ajouterFichiers(event.target.files); event.target.value = '' }} />
            <span>JPG, PNG, PDF · 5 Mo maximum au total</span>
          </div>
          {fichiers.length > 0 && <ul className="reclamation__fichiers">{fichiers.map((fichier, index) => <li key={`${fichier.name}-${index}`}>{fichier.name} <button type="button" onClick={() => setFichiers(fichiers.filter((_, i) => i !== index))} aria-label={`Retirer ${fichier.name}`}>Retirer</button></li>)}</ul>}
          {erreurFichier && <p role="alert" className="reclamation__erreur">{erreurFichier}</p>}
          <fieldset className="reclamation__priorites"><legend>Priorité</legend>{Object.entries(PRIORITES).map(([value, label]) => <label key={value} className={form.priorite === value ? 'selectionnee' : ''}><input type="radio" name="priorite" value={value} checked={form.priorite === value} onChange={() => setForm({ ...form, priorite: value })} />{label}</label>)}</fieldset>
          {assistant?.priorite_suggeree && <p className="reclamation__suggestion">Priorité suggérée : {PRIORITES[assistant.priorite_suggeree]}. Vous pouvez la modifier.</p>}
          {erreur && <p role="alert" className="reclamation__erreur">{erreur}</p>}
          </div>
          <aside className="reclamation__assistant" aria-live="polite">
            <h3><span aria-hidden="true">IA</span> Assistant</h3>
            <p>Gemini analyse et peut reformuler le texte saisi. L’objet et la description sont transmis à Google; les pièces jointes ne le sont pas.</p>
            {assistantEnCours && <p role="status">Analyse du texte…</p>}
            {assistantErreur && <p role="alert" className="reclamation__erreur">{assistantErreur}</p>}
            {assistant ? <>
              <section><h4>Motif suggéré</h4><p>{TYPES[assistant.motif_suggere] || 'Autre'} · priorité {PRIORITES[assistant.priorite_suggeree]}</p><small>{assistant.raison_priorite}</small><button type="button" className="bouton bouton--assistant" onClick={() => setForm((precedent) => ({ ...precedent, type: assistant.motif_suggere, priorite: assistant.priorite_suggeree }))}>Appliquer les suggestions</button></section>
              <section><h4>Annonces du même propriétaire</h4><p>{assistant.signalements_recents_meme_proprietaire ? `${assistant.signalements_recents_meme_proprietaire} autre(s) annonce(s) signalée(s) récemment.` : 'Aucun autre signalement récent détecté.'}</p>{assistant.annonces_similaires?.map((annonce, index) => <small key={`${annonce.titre}-${index}`}>{annonce.titre} · {annonce.date}</small>)}</section>
              <section><h4>Pièces utiles à vérifier</h4><ul>{assistant.pieces_a_fournir?.map((piece) => <li key={piece}>{piece}</li>)}</ul></section>
              <p className="reclamation__conseil">{assistant.conseil}</p>
            </> : <p>Décrivez les faits pour obtenir des pistes et des pièces utiles à vérifier.</p>}
            <small>Les suggestions ne déterminent aucune décision; le modérateur examine le dossier.</small>
          </aside>
          <footer className="reclamation__form-actions">
            <button type="button" className="bouton" onClick={fermer}>Annuler</button>
            <button type="submit" className="bouton bouton--principal" disabled={chargement}>{chargement ? 'Envoi…' : 'Déposer la réclamation'}</button>
          </footer>
        </form>
      </section>
    </div>
  )
}

function DetailReclamation({ reclamation, fermer, actualiser }) {
  const [message, setMessage] = useState('')
  const [statut, setStatut] = useState(reclamation.statut)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function changerStatut(event) {
    setStatut(event.target.value)
    setErreur('')
    try {
      const miseAJour = await modifierReclamation(reclamation.id, { statut: event.target.value })
      actualiser(miseAJour)
    } catch (error) {
      setErreur(lireErreur(error).message)
      setStatut(reclamation.statut)
    }
  }

  async function envoyerMessage(event) {
    event.preventDefault()
    if (!message.trim()) return
    setEnCours(true)
    setErreur('')
    try {
      const miseAJour = await ajouterMessageReclamation(reclamation.id, message.trim())
      actualiser(miseAJour)
      setMessage('')
    } catch (error) {
      setErreur(lireErreur(error).message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="reclamation__voile" onMouseDown={(event) => event.target === event.currentTarget && fermer()}>
      <section className="reclamation__dialogue" role="dialog" aria-modal="true" aria-labelledby="reclamation-detail-titre">
        <header className="reclamation__dialogue-entete">
          <div>
            <p className="reclamation__reference">{reclamation.reference}</p>
            <h2 id="reclamation-detail-titre">{reclamation.objet}</h2>
          </div>
          <button type="button" className="reclamation__fermer" onClick={fermer} aria-label="Fermer">
            ×
          </button>
        </header>
        <div className="reclamation__dialogue-corps">
          <dl className="reclamation__details">
            <div><dt>Auteur</dt><dd>{reclamation.auteur_nom || 'Utilisateur'}{reclamation.auteur_email ? ` · ${reclamation.auteur_email}` : ''}</dd></div>
            <div><dt>Annonce</dt><dd>{reclamation.titre_annonce || 'Aucune annonce associée'}</dd></div>
            <div><dt>Type</dt><dd>{TYPES[reclamation.type] || reclamation.type}</dd></div>
            <div><dt>Priorité</dt><dd>{PRIORITES[reclamation.priorite] || reclamation.priorite}</dd></div>
            <div><dt>Créée le</dt><dd>{formaterDateHeure(reclamation.date_creation)}</dd></div>
          </dl>
          <p className="reclamation__description">{reclamation.description}</p>
          {reclamation.pieces_jointes?.length > 0 && <section className="reclamation__pieces-detail"><h3>Pièces jointes</h3><ul>{reclamation.pieces_jointes.map((piece, index) => <li key={`${piece.fichier || piece}-${index}`}><a href={`/api/reclamations/${reclamation.id}/pieces-jointes/${encodeURIComponent(piece.fichier || piece)}`}>{piece.nom || piece}</a></li>)}</ul></section>}
          <div className="reclamation__traitement">
            <label htmlFor="reclamation-statut">Statut</label>
            <select id="reclamation-statut" value={statut} onChange={changerStatut}>
              {Object.entries(STATUTS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </div>
          <h3>Messages</h3>
          {reclamation.messages?.length ? (
            <ol className="reclamation__messages">
              {reclamation.messages.map((item) => (
                <li key={item.id}>
                  <strong>{item.auteur_nom || 'Utilisateur'}</strong>
                  <time>{formaterDateHeure(item.date_envoi)}</time>
                  <p>{item.message}</p>
                </li>
              ))}
            </ol>
          ) : <p className="texte-secondaire">Aucun message pour le moment.</p>}
          <form className="reclamation__reponse" onSubmit={envoyerMessage}>
            <label htmlFor="reclamation-message">Ajouter un message</label>
            <textarea id="reclamation-message" rows="3" value={message} onChange={(event) => setMessage(event.target.value)} />
            <button className="bouton bouton--principal" type="submit" disabled={enCours || !message.trim()}>
              {enCours ? 'Envoi…' : 'Envoyer'}
            </button>
          </form>
          {erreur && <p className="reclamation__erreur" role="alert">{erreur}</p>}
        </div>
      </section>
    </div>
  )
}

/** Liste de modération des signalements, avec filtres, consultation, réponse et suppression. */
export default function ReclamationsPage() {
  const { etat, donnees, erreur, reessayer, modifierDonnees } = useRequete('reclamations', () =>
    listerReclamations({ page: 1, per_page: 50 }),
  )
  const [recherche, setRecherche] = useState('')
  const [statut, setStatut] = useState('')
  const [type, setType] = useState('')
  const [priorite, setPriorite] = useState('')
  const [page, setPage] = useState(1)
  const [selection, setSelection] = useState(null)
  const [nouvelle, setNouvelle] = useState(false)
  const [aSupprimer, setASupprimer] = useState(null)
  const [suppression, setSuppression] = useState(false)
  const [erreurAction, setErreurAction] = useState('')
  const [triAssistant, setTriAssistant] = useState(false)
  const [brouillon, setBrouillon] = useState('')
  const [assistantTraitement, setAssistantTraitement] = useState(null)
  const [assistantTraitementErreur, setAssistantTraitementErreur] = useState('')
  const parPage = 5

  const items = donnees?.items ?? AUCUNE_RECLAMATION
  const visibles = useMemo(() => {
    const terme = recherche.trim().toLocaleLowerCase('fr')
    return items.filter((item) => {
      const correspondTexte = !terme || [item.reference, item.objet, item.titre_annonce, item.auteur_nom]
        .some((valeur) => String(valeur || '').toLocaleLowerCase('fr').includes(terme))
      return correspondTexte && (!statut || item.statut === statut) && (!type || item.type === type) &&
        (!priorite || item.priorite === priorite)
    })
  }, [items, recherche, statut, type, priorite])
  const nbPages = Math.max(1, Math.ceil(visibles.length / parPage))
  const pageCourante = Math.min(page, nbPages)
  const ordonnes = useMemo(() => triAssistant ? [...visibles].sort((a, b) => {
    const rang = { urgente: 0, haute: 1, normale: 2, basse: 3 }
    return (rang[a.priorite] ?? 4) - (rang[b.priorite] ?? 4) || new Date(b.date_creation) - new Date(a.date_creation)
  }) : visibles, [visibles, triAssistant])
  const lignes = ordonnes.slice((pageCourante - 1) * parPage, pageCourante * parPage)
  const doublons = useMemo(() => items.reduce((acc, item) => {
    if (['resolue', 'rejetee', 'cloturee'].includes(item.statut)) return acc
    const cle = `${item.annonce_id || 'sans-annonce'}:${item.type}`
    acc[cle] = [...(acc[cle] || []), item]
    return acc
  }, {}), [items])
  const groupesDoublons = Object.values(doublons).filter((groupe) => groupe.length > 1)
  const aTraiter = items.find((item) => ['nouvelle', 'en_cours', 'en_attente_info'].includes(item.statut))

  useEffect(() => {
    if (!aTraiter) return undefined
    let actif = true
    analyserAssistantReclamation({ annonce_id: aTraiter.annonce_id, objet: aTraiter.objet, description: aTraiter.description })
      .then((resultat) => { if (actif) { setAssistantTraitementErreur(''); setAssistantTraitement(resultat); setBrouillon(resultat.brouillon_reponse || '') } })
      .catch((error) => { if (actif) { setAssistantTraitement(null); setAssistantTraitementErreur(lireErreur(error).message) } })
    return () => { actif = false }
  }, [aTraiter])
  const comptes = items.reduce((acc, item) => {
    acc[item.statut] = (acc[item.statut] || 0) + 1
    if (item.priorite === 'urgente') acc.urgentes += 1
    return acc
  }, { urgentes: 0 })

  async function confirmerSuppression() {
    if (!aSupprimer) return
    setSuppression(true)
    setErreurAction('')
    try {
      await supprimerReclamation(aSupprimer.id)
      modifierDonnees((precedent) => ({ ...precedent, items: precedent.items.filter((item) => item.id !== aSupprimer.id), total: Math.max(0, precedent.total - 1) }))
      setASupprimer(null)
    } catch (error) {
      setErreurAction(lireErreur(error).message)
    } finally {
      setSuppression(false)
    }
  }

  function actualiserReclamation(miseAJour) {
    modifierDonnees((precedent) => ({ ...precedent, items: precedent.items.map((item) => item.id === miseAJour.id ? miseAJour : item) }))
    setSelection(miseAJour)
  }

  return (
    <section className="page reclamation">
      <div className="page__entete">
        <div>
          <h1>Gestion des réclamations</h1>
          <p className="texte-secondaire">Consultez et traitez les signalements reçus.</p>
        </div>
        <button type="button" className="bouton bouton--principal" onClick={() => setNouvelle(true)}>+ Nouvelle réclamation</button>
      </div>

      {etat === 'chargement' && <p className="etat" role="status">Chargement des réclamations…</p>}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && <>
        <div className="reclamation__indicateurs">
          <div><span>Nouvelles</span><strong className="reclamation__valeur--nouvelle">{comptes.nouvelle || 0}</strong></div>
          <div><span>En cours</span><strong className="reclamation__valeur--cours">{comptes.en_cours || 0}</strong></div>
          <div><span>Résolues</span><strong className="reclamation__valeur--resolue">{comptes.resolue || 0}</strong></div>
          <div><span>Urgentes</span><strong className="reclamation__valeur--urgente">{comptes.urgentes}</strong></div>
        </div>

        <div className="reclamation__filtres" role="search" aria-label="Filtres des réclamations">
          <label className="visuellement-cache" htmlFor="filtre-reclamation-recherche">Recherche</label>
          <input id="filtre-reclamation-recherche" type="search" placeholder="Référence, objet, annonce…" value={recherche} onChange={(event) => { setRecherche(event.target.value); setPage(1) }} />
          <label className="visuellement-cache" htmlFor="filtre-reclamation-statut">Statut</label>
          <select id="filtre-reclamation-statut" value={statut} onChange={(event) => { setStatut(event.target.value); setPage(1) }}>
            <option value="">Statut : Tous</option>
            {Object.entries(STATUTS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <label className="visuellement-cache" htmlFor="filtre-reclamation-type">Type</label>
          <select id="filtre-reclamation-type" value={type} onChange={(event) => { setType(event.target.value); setPage(1) }}>
            <option value="">Type : Tous</option>
            {Object.entries(TYPES).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <label className="visuellement-cache" htmlFor="filtre-reclamation-priorite">Priorité</label>
          <select id="filtre-reclamation-priorite" value={priorite} onChange={(event) => { setPriorite(event.target.value); setPage(1) }}>
            <option value="">Priorité : Toutes</option>
            {Object.entries(PRIORITES).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
          <button type="button" className="bouton bouton--principal" onClick={() => setPage(1)}>Rechercher</button>
        </div>

        {erreurAction && <p role="alert" className="reclamation__erreur">{erreurAction}</p>}
        <div className="reclamation__table-enveloppe">
          <table className="reclamation__table">
            <thead><tr><th scope="col">Réf.</th><th scope="col">Objet</th><th scope="col">Annonce</th><th scope="col">Type</th><th scope="col">Priorité</th><th scope="col">Statut</th><th scope="col"><span className="visuellement-cache">Actions</span></th></tr></thead>
            <tbody>
              {lignes.map((item) => <tr key={item.id}>
                <td><strong>{item.reference}</strong></td>
                <td>{item.objet}</td>
                <td>{item.titre_annonce || '—'}</td>
                <td><span className={`reclamation__badge reclamation__type ${classeType(item.type)}`}>{TYPES[item.type] || item.type}</span></td>
                <td><span className={`reclamation__badge ${classePriorite(item.priorite)}`}>{PRIORITES[item.priorite] || item.priorite}</span></td>
                <td><span className={`reclamation__badge ${classeStatut(item.statut)}`}>{STATUTS[item.statut] || item.statut}</span></td>
                <td className="reclamation__actions"><button type="button" className="bouton reclamation__voir" onClick={() => setSelection(item)}>Voir</button><button type="button" className="bouton reclamation__supprimer" onClick={() => setASupprimer(item)} aria-label={`Supprimer ${item.reference}`}>Supprimer</button></td>
              </tr>)}
              {lignes.length === 0 && <tr><td colSpan="7" className="reclamation__vide">Aucune réclamation ne correspond aux filtres.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="reclamation__pagination">
          <span>Affichage {visibles.length ? (pageCourante - 1) * parPage + 1 : 0}–{Math.min(pageCourante * parPage, visibles.length)} sur {visibles.length}</span>
          <div>
            <button type="button" className="bouton" onClick={() => setPage((n) => Math.max(1, n - 1))} disabled={pageCourante === 1} aria-label="Page précédente">‹</button>
            {Array.from({ length: nbPages }, (_, index) => <button type="button" className={`bouton${pageCourante === index + 1 ? ' bouton--principal' : ''}`} key={index + 1} onClick={() => setPage(index + 1)} aria-current={pageCourante === index + 1 ? 'page' : undefined}>{index + 1}</button>)}
            <button type="button" className="bouton" onClick={() => setPage((n) => Math.min(nbPages, n + 1))} disabled={pageCourante === nbPages} aria-label="Page suivante">›</button>
          </div>
        </div>
        <section className="reclamation__traitement-assistant" aria-labelledby="assistant-traitement-titre">
          <header><h2 id="assistant-traitement-titre"><span aria-hidden="true">IA</span> Assistant de traitement des réclamations</h2><p>Gemini analyse le texte de la réclamation; propositions à valider par le modérateur.</p></header>
          <div className="reclamation__traitement-grille">
            <article><h3>1. Tri automatique</h3><p><strong>{comptes.nouvelle || 0} nouvelle(s) réclamation(s).</strong> Le tri par priorité peut aider à organiser la file.</p><button type="button" className="bouton bouton--assistant" aria-pressed={triAssistant} onClick={() => { setTriAssistant(!triAssistant); setPage(1) }}>{triAssistant ? 'Désactiver le tri prioritaire' : 'Trier par priorité'}</button></article>
            <article><h3>2. Doublons et regroupement</h3>{groupesDoublons.length ? groupesDoublons.map((groupe) => <p key={`${groupe[0].annonce_id}-${groupe[0].type}`}>{groupe.length} signalements actifs concernant « {groupe[0].titre_annonce || 'une annonce'} » · {TYPES[groupe[0].type] || groupe[0].type} ({groupe.map((r) => r.reference).join(', ')}).</p>) : <p>Aucun doublon exact détecté parmi les signalements actifs.</p>}<small>Regroupement indicatif par annonce et motif; à vérifier.</small></article>
            <article><h3>3. Brouillon de réponse</h3>{aTraiter ? <>{assistantTraitementErreur ? <p className="reclamation__erreur" role="alert">{assistantTraitementErreur}</p> : assistantTraitement ? <><p>Pour {aTraiter.reference} · brouillon proposé par Gemini, modifiable avant enregistrement.</p><textarea aria-label="Brouillon de réponse" rows="4" value={brouillon} onChange={(event) => setBrouillon(event.target.value)} /><button type="button" className="bouton bouton--assistant" disabled={!brouillon.trim()} onClick={async () => { try { const maj = await modifierReclamation(aTraiter.id, { reponse_admin: brouillon }); actualiserReclamation(maj) } catch (error) { setErreurAction(lireErreur(error).message) } }}>Enregistrer le brouillon</button></> : <p role="status">Gemini analyse le texte de la réclamation…</p>}</> : <p>Aucune réclamation à traiter pour le moment.</p>}</article>
            <article><h3>4. Suggestions de vérification</h3>{assistantTraitementErreur ? <p className="reclamation__erreur">{assistantTraitementErreur}</p> : assistantTraitement ? <><p>{assistantTraitement.pieces_a_fournir?.slice(0, 2).join(' · ')}</p>{assistantTraitement.doublon_possible && <p>Un signalement actif de même motif existe pour cette annonce.</p>}<small>{assistantTraitement.mention}</small></> : <p>Gemini analyse le texte de la réclamation…</p>}</article>
          </div>
          <p className="reclamation__note-assistant">L’assistant ne modifie ni ne suspend une annonce et ne tranche pas un dossier. Toute décision finale revient au modérateur.</p>
        </section>
      </>}

      {nouvelle && <NouvelleReclamation fermer={() => setNouvelle(false)} creee={(item) => { modifierDonnees((precedent) => ({ ...precedent, items: [item, ...precedent.items], total: precedent.total + 1 })); setNouvelle(false) }} />}
      {selection && <DetailReclamation reclamation={selection} fermer={() => setSelection(null)} actualiser={actualiserReclamation} />}
      <ModalConfirmation
        ouvert={Boolean(aSupprimer)}
        titre="Supprimer la réclamation ?"
        message={aSupprimer ? `La réclamation ${aSupprimer.reference} sera supprimée définitivement.` : ''}
        onConfirmer={confirmerSuppression}
        onAnnuler={() => setASupprimer(null)}
        chargement={suppression}
      />
    </section>
  )
}
