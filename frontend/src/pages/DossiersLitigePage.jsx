import { useEffect, useRef, useState } from 'react'
import {
  ajouterPieceLitige, corrigerClassificationLitige, creerDossierLitige, creerRapportLitige, listerDossiersLitige,
  modifierMetadonneesPiece, obtenirChronologieLitige, obtenirComptesLitige,
  obtenirContradictionsLitige, obtenirDossierLitige, obtenirPreuvesLitige, obtenirPreuvesNonIdentifiees,
  obtenirRapportLitige, obtenirConfigurationLitige, poserQuestionLitige,
  rechercherPreuvesLitige, supprimerDossierLitige, supprimerPieceLitige,
  telechargerRapportLitige,
} from '../api/dossiersLitige'
import { useRequete } from '../hooks/useRequete'
import './DossiersLitigePage.css'

const ONGLETS = [
  { id: 'pieces', titre: 'Documents' },
  { id: 'preuves', titre: 'Preuves' },
  { id: 'chronologie', titre: 'Chronologie' },
  { id: 'parties', titre: 'Comptes des parties' },
  { id: 'recherche', titre: 'Recherche et questions' },
  { id: 'rapport', titre: 'Rapports' },
  { id: 'limites', titre: 'Configuration et limites' },
]
const ROLES = [
  ['unknown', 'Inconnu'], ['tenant', 'Locataire'], ['landlord', 'Propriétaire'],
  ['both_parties', 'Deux parties'], ['payment_provider', 'Prestataire de paiement'],
  ['contractor', 'Artisan'], ['other', 'Autre'],
]
const TYPES = [
  ['payment_record', 'Preuve de paiement'], ['lease_clause', 'Clause de bail'],
  ['condition_report', 'État des lieux'], ['repair_record', 'Réparation'],
  ['notice', 'Avis ou préavis'], ['party_statement', 'Déclaration'], ['correspondence', 'Correspondance'], ['other', 'Autre'],
]
const AVERTISSEMENT = 'Outil d’organisation et de recherche documentaire. Il ne fournit pas de conseil juridique, ne détermine pas qui a raison et ne prédit pas l’issue d’une procédure. Les pièces ne sont pas authentifiées.'

function dateCourte(value) {
  if (!value) return 'Date non indiquée'
  const iso = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`
  return value
}

function messageErreur(error, fallback) {
  return error?.response?.data?.message || fallback
}

export default function DossiersLitigePage() {
  const [selection, setSelection] = useState('')
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [langue, setLangue] = useState('fr')
  const [question, setQuestion] = useState('')
  const [reponse, setReponse] = useState(null)
  const [recherche, setRecherche] = useState(null)
  const [preuves, setPreuves] = useState([])
  const [chronologie, setChronologie] = useState([])
  const [comptes, setComptes] = useState({ tenant: [], landlord: [] })
  const [contradictions, setContradictions] = useState([])
  const [nonIdentifiees, setNonIdentifiees] = useState([])
  const [configuration, setConfiguration] = useState(null)
  const [detailCase, setDetailCase] = useState(null)
  const [onglet, setOnglet] = useState('pieces')
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [nomAuteur, setNomAuteur] = useState('')
  const [roleAuteur, setRoleAuteur] = useState('unknown')
  const [dateDocument, setDateDocument] = useState('')
  const [filtres, setFiltres] = useState({ author: '', author_role: '', evidence_type: '', date_from: '', date_to: '', confidence_min: '' })
  const inputFichier = useRef(null)
  const { donnees: dossiers, erreur: erreurChargement, reessayer } = useRequete('dossiers-litige', listerDossiersLitige)
  const listeDossiers = dossiers || []
  const resumeActif = listeDossiers.find((d) => d.id === selection) || listeDossiers[0]
  const caseId = resumeActif?.case_id || resumeActif?.id
  const actif = resumeActif?.legacy ? resumeActif : (detailCase?.id === resumeActif?.id ? detailCase : resumeActif)
  const pieces = actif?.documents || []

  useEffect(() => {
    if (!resumeActif || resumeActif.legacy) return undefined
    let mounted = true
    obtenirDossierLitige(caseId).then((detail) => { if (mounted) setDetailCase(detail) })
      .catch((error) => { if (mounted) setErreur(messageErreur(error, 'Chargement du dossier impossible.')) })
    return () => { mounted = false }
  }, [caseId, resumeActif])

  async function rechargerCase() {
    if (!caseId || actif?.legacy) return
    try { setDetailCase(await obtenirDossierLitige(caseId)) }
    catch (error) { setErreur(messageErreur(error, 'Actualisation du dossier impossible.')) }
  }

  useEffect(() => {
    obtenirConfigurationLitige().then(setConfiguration).catch(() => setConfiguration(null))
  }, [])

  async function creer(event) {
    event.preventDefault()
    setErreur('')
    try {
      const nouveau = await creerDossierLitige({ titre, description, langue })
      setSelection(nouveau.case_id || nouveau.id)
      setTitre('')
      setDescription('')
      setReponse(null)
      setRecherche(null)
      setOnglet('pieces')
      reessayer()
    } catch (error) { setErreur(messageErreur(error, 'Création du dossier impossible.')) }
  }

  async function importerFichier(fichier) {
    if (!fichier || !actif || actif.legacy) return
    setChargement(true)
    setErreur('')
    try {
      await ajouterPieceLitige(caseId, fichier, {
        auteur: nomAuteur, role_auteur: roleAuteur, date_document: dateDocument,
      })
      reessayer()
      await rechargerCase()
      await actualiser(onglet)
    } catch (error) { setErreur(messageErreur(error, 'Import du document impossible.')) }
    finally { setChargement(false) }
  }

  async function importer(event) {
    const fichier = event.target.files?.[0]
    event.target.value = ''
    await importerFichier(fichier)
  }

  async function actualiser(identifiant = onglet, overrides = filtres) {
    if (!caseId || actif?.legacy) return
    try {
      if (identifiant === 'preuves') setPreuves((await obtenirPreuvesLitige(caseId, overrides)).items || [])
      if (identifiant === 'chronologie') setChronologie((await obtenirChronologieLitige(caseId)).items || [])
      if (identifiant === 'parties') setComptes((await obtenirComptesLitige(caseId)).items || { tenant: [], landlord: [] })
      if (identifiant === 'rapport') {
        const [rapport, manquants, oppositions] = await Promise.all([
          obtenirRapportLitige(caseId), obtenirPreuvesNonIdentifiees(caseId), obtenirContradictionsLitige(caseId),
        ])
        setNonIdentifiees(manquants.items || [])
        setContradictions(oppositions.items || [])
        setChronologie(rapport.timeline || rapport.chronologie || [])
      }
      setErreur('')
    } catch (error) { setErreur(messageErreur(error, 'Chargement des informations impossible.')) }
  }

  async function abrirOnglet(id) {
    setOnglet(id)
    if (id === 'limites') return
    await actualiser(id)
  }

  async function rechercherPreuves(event) {
    event.preventDefault()
    if (!caseId || !question.trim()) return
    setChargement(true)
    setErreur('')
    try {
      setRecherche(await rechercherPreuvesLitige(caseId, question.trim()))
    } catch (error) { setErreur(messageErreur(error, 'Recherche impossible.')) }
    finally { setChargement(false) }
  }

  async function demanderReponse(event) {
    event.preventDefault()
    if (!caseId || !question.trim()) return
    setChargement(true)
    setErreur('')
    try { setReponse(await poserQuestionLitige(caseId, question.trim())) }
    catch (error) { setErreur(messageErreur(error, 'Réponse indisponible.')) }
    finally { setChargement(false) }
  }

  async function genererRapport(format) {
    if (!caseId) return
    setChargement(true)
    setErreur('')
    try {
      const report = await creerRapportLitige(caseId, format)
      const blob = await telechargerRapportLitige(report.download_url)
      const url = URL.createObjectURL(blob)
      const lien = document.createElement('a')
      lien.href = url
      lien.download = `rapport-litige-${caseId}.${format === 'markdown' ? 'md' : format}`
      lien.click()
      URL.revokeObjectURL(url)
    } catch (error) { setErreur(messageErreur(error, 'Génération du rapport impossible.')) }
    finally { setChargement(false) }
  }

  async function supprimerCase() {
    if (!caseId || !window.confirm('Supprimer définitivement ce dossier et les documents privés associés ?')) return
    setChargement(true)
    try {
      await supprimerDossierLitige(caseId)
      setSelection('')
      setReponse(null)
      reessayer()
    } catch (error) { setErreur(messageErreur(error, 'Suppression impossible.')) }
    finally { setChargement(false) }
  }

  async function supprimerDocument(id) {
    if (!window.confirm('Supprimer le document original et ses passages ?')) return
    try {
      await supprimerPieceLitige(caseId, id)
      reessayer()
      await rechargerCase()
      await actualiser(onglet)
    } catch (error) { setErreur(messageErreur(error, 'Suppression du document impossible.')) }
  }

  async function enregistrerMetadonnees(documentId, form) {
    const donnees = Object.fromEntries(new FormData(form).entries())
    try {
      await modifierMetadonneesPiece(caseId, documentId, donnees)
      reessayer()
      await rechargerCase()
      setErreur('')
    } catch (error) { setErreur(messageErreur(error, 'Modification des métadonnées impossible.')) }
  }

  async function corrigerPreuve(event, chunkId) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget).entries())
    try {
      await corrigerClassificationLitige(caseId, chunkId, data)
      await actualiser('preuves')
    } catch (error) { setErreur(messageErreur(error, 'Correction de la classification impossible.')) }
  }

  if (erreurChargement) return <main className="dossiers-litige"><p role="alert">{erreurChargement.message}</p></main>

  return (
    <main className="dossiers-litige" aria-labelledby="titre-dossiers-litige">
      <header className="dossiers-litige__intro">
        <h1 id="titre-dossiers-litige">Dossiers de litige locatif</h1>
        <p>Organisez les pièces, retrouvez les sources et préparez une revue humaine.</p>
      </header>
      <aside className="dossiers-litige__avis" role="note"><strong>Information importante.</strong> {AVERTISSEMENT}</aside>
      <p className="dossiers-litige__confidentialite">Les documents et recherches sont traités localement et restent isolés par compte et par dossier. Aucun document n’est transmis à Gemini ou à un autre service externe.</p>
      {(erreur || erreurChargement?.message) && <p className="dossiers-litige__erreur" role="alert">{erreur || erreurChargement.message}</p>}

      <div className="dossiers-litige__mise-en-page">
        <aside className="dossiers-litige__panneau dossiers-litige__liste" aria-label="Mes dossiers">
          <h2>Mes dossiers</h2>
          <form onSubmit={creer} className="dossiers-litige__creation">
            <label htmlFor="titre-dossier-litige">Titre du dossier</label>
            <input id="titre-dossier-litige" value={titre} onChange={(e) => setTitre(e.target.value)} maxLength={160} required placeholder="Ex. Retenue sur le dépôt" />
            <label htmlFor="description-dossier-litige">Description</label>
            <textarea id="description-dossier-litige" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} rows={2} />
            <label htmlFor="langue-dossier-litige">Langue</label>
            <select id="langue-dossier-litige" value={langue} onChange={(e) => setLangue(e.target.value)}><option value="fr">Français</option><option value="en">English</option></select>
            <button className="bouton bouton--principal" type="submit" disabled={chargement}>+ Créer le dossier</button>
          </form>
          {listeDossiers.length ? <ul className="dossiers-litige__cartes">
            {listeDossiers.map((dossier) => <li key={dossier.id}>
              <button type="button" className={`dossiers-litige__carte${actif?.id === dossier.id ? ' est-actif' : ''}`} onClick={() => { setSelection(dossier.id); setReponse(null); setRecherche(null); setOnglet('pieces') }} aria-current={actif?.id === dossier.id ? 'page' : undefined}>
                <strong>{dossier.titre || dossier.nom}</strong>
                <span>{dossier.documents?.length || 0} document(s) · {dateCourte(dossier.cree_le?.slice(0, 10))}</span>
              </button>
            </li>)}
          </ul> : <p className="dossiers-litige__vide">Créez un dossier pour commencer.</p>}
        </aside>

        {actif ? <section className="dossiers-litige__contenu" aria-label={`Dossier ${actif.titre || actif.nom}`}>
          <header className="dossiers-litige__panneau dossiers-litige__entete-dossier">
            <div><h2>{actif.titre || actif.nom}</h2><p>{actif.description}</p></div>
            <button type="button" className="bouton bouton--danger" onClick={supprimerCase} disabled={chargement}>Supprimer le dossier</button>
            <div className="dossiers-litige__badges"><span className="dossiers-litige__badge">{pieces.length} document(s)</span><span className="dossiers-litige__badge">{pieces.reduce((total, item) => total + (item.passages?.length || 0), 0)} passages</span></div>
          </header>

          <div className="dossiers-litige__onglets" role="tablist" aria-label="Contenu du dossier">
            {ONGLETS.map((item) => <button key={item.id} role="tab" type="button" id={`onglet-litige-${item.id}`} aria-selected={onglet === item.id} aria-controls={`panneau-litige-${item.id}`} onClick={() => abrirOnglet(item.id)}>{item.titre}</button>)}
          </div>

          <section className="dossiers-litige__panneau dossiers-litige__zone" role="tabpanel" id={`panneau-litige-${onglet}`} aria-labelledby={`onglet-litige-${onglet}`}>
            {onglet === 'pieces' && <>
              <h3>Importer une pièce privée</h3>
              {actif.legacy ? <p className="dossiers-litige__confidentialite">Ancien dossier conservé en lecture. Créez un nouveau dossier pour importer les formats et métadonnées actuels.</p> : <>
                <div className="dossiers-litige__metadonnees-import">
                  <label>Auteur<input value={nomAuteur} maxLength={160} onChange={(e) => setNomAuteur(e.target.value)} /></label>
                  <label>Rôle de l’auteur<select value={roleAuteur} onChange={(e) => setRoleAuteur(e.target.value)}>{ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <label>Date du document<input type="date" value={dateDocument} onChange={(e) => setDateDocument(e.target.value)} /></label>
                </div>
                <button type="button" className="dossiers-litige__depot" onClick={() => inputFichier.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); importerFichier(event.dataTransfer.files?.[0]) }} disabled={chargement}>
                  <strong>{chargement ? 'Import en cours…' : 'Glissez un document ici'}</strong><span>PDF, DOCX, TXT, Markdown, EML ou JSON · 4 Mo maximum</span><span className="bouton bouton--secondaire">Choisir un fichier</span>
                </button>
                <input ref={inputFichier} className="visuellement-cache" id="piece-litige" type="file" accept=".pdf,.docx,.txt,.md,.markdown,.eml,.json" onChange={importer} disabled={chargement} aria-label="Ajouter un document de preuve" />
              </>}
              <p className="dossiers-litige__confidentialite">Les documents originaux sont conservés hors du dossier public. Les fichiers sont traités localement et ne sont jamais envoyés vers une API d’IA externe.</p>
              {pieces.length ? <div className="dossiers-litige__documents">
                {pieces.map((piece) => <article className="dossiers-litige__document" key={piece.id}>
                  <header><div><h4>{piece.titre || piece.nom}</h4><span>{piece.role_auteur || 'Auteur inconnu'} · {piece.passages?.length || 0} passages</span></div>
                    {!actif.legacy && <button className="bouton bouton--danger" type="button" onClick={() => supprimerDocument(piece.id)}>Supprimer</button>}
                  </header>
                  {!actif.legacy && <details><summary>Modifier les métadonnées</summary><form onSubmit={(event) => { event.preventDefault(); enregistrerMetadonnees(piece.id, event.currentTarget) }}>
                    <label>Titre<input name="title" defaultValue={piece.titre || piece.nom} maxLength={255} required /></label>
                    <label>Auteur<input name="author" defaultValue={piece.auteur || ''} maxLength={160} /></label>
                    <label>Rôle<select name="author_role" defaultValue={piece.role_auteur || 'unknown'}>{ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                    <label>Date du document<input name="document_date" type="date" defaultValue={piece.date_document || ''} /></label>
                    <button className="bouton bouton--secondaire" type="submit">Enregistrer</button>
                  </form></details>}
                  {!actif.legacy && <a href={`/api/dossiers-litige/${encodeURIComponent(caseId)}/documents/${piece.id}/fichier`}>Télécharger le document original</a>}
                  <ul>{(piece.passages || []).slice(0, 2).map((p) => <li key={p.chunk_id || p.id}><blockquote>{p.texte}</blockquote><small>Passage {p.chunk_id || p.id} · page {p.page || '—'} · <strong>à vérifier humainement</strong></small></li>)}</ul>
                </article>)}
              </div> : <p className="dossiers-litige__vide">Aucun document importé dans ce dossier.</p>}
            </>}

            {onglet === 'preuves' && <>
              <h3>Inventaire des passages</h3>
              <form className="dossiers-litige__filtres" onSubmit={(event) => { event.preventDefault(); actualiser('preuves', filtres) }}>
                <label>Auteur<input value={filtres.author} onChange={(e) => setFiltres({ ...filtres, author: e.target.value })} maxLength={160} /></label>
                <label>Rôle<select value={filtres.author_role} onChange={(e) => setFiltres({ ...filtres, author_role: e.target.value })}><option value="">Tous</option>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
                <label>Type<select value={filtres.evidence_type} onChange={(e) => setFiltres({ ...filtres, evidence_type: e.target.value })}><option value="">Tous</option>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
                <label>À partir du<input type="date" value={filtres.date_from} onChange={(e) => setFiltres({ ...filtres, date_from: e.target.value })} /></label>
                <label>Jusqu’au<input type="date" value={filtres.date_to} onChange={(e) => setFiltres({ ...filtres, date_to: e.target.value })} /></label>
                <label>Score minimum<select value={filtres.confidence_min} onChange={(e) => setFiltres({ ...filtres, confidence_min: e.target.value })}><option value="">Tous</option><option value="0.5">50 %</option><option value="0.7">70 %</option><option value="0.85">85 %</option></select></label>
                <button className="bouton bouton--principal" type="submit">Filtrer</button>
              </form>
              {preuves.length ? <ul className="dossiers-litige__sources">{preuves.map((p) => <li key={p.chunk_id}><header><strong>{p.nom_fichier} · {p.chunk_id}</strong><span>{p.type_preuve} · {p.sujet} · {p.role_auteur}</span></header><blockquote>{p.texte}</blockquote><small>Score indicatif {Math.round((p.score_classification || 0) * 100)} % · vérification humaine requise · offsets {p.debut}–{p.fin}</small><form className="dossiers-litige__correction" onSubmit={(event) => corrigerPreuve(event, p.chunk_id)}><label>Type confirmé<select name="evidence_type" defaultValue={p.type_preuve}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label><label>Sujet<select name="issue" defaultValue={p.sujet}>{['deposit', 'rent_arrears', 'repairs', 'notice', 'utilities', 'access', 'other'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label><button className="bouton bouton--secondaire" type="submit">Valider la classification</button></form></li>)}</ul> : <p className="dossiers-litige__vide">Aucun passage ne correspond aux filtres. Cela ne signifie pas que la preuve n’existe pas.</p>}
            </>}

            {onglet === 'chronologie' && <>
              <h3>Dates explicitement extraites</h3>
              {chronologie.length ? <ol className="dossiers-litige__chronologie">{chronologie.map((item, i) => <li key={`${item.chunk_id || item.source}-${i}`}><time>{dateCourte(item.date)}</time><blockquote>{item.quote || item.event || item.citation}</blockquote><small>{item.source} · {item.author_role || item.auteur || 'auteur inconnu'} · non vérifié</small></li>)}</ol> : <p className="dossiers-litige__vide">Aucune date complète et valide n’a été extraite.</p>}
            </>}

            {onglet === 'parties' && <>
              <h3>Déclarations attribuées par les métadonnées</h3>
              <div className="dossiers-litige__parties">{[['tenant', 'Locataire'], ['landlord', 'Propriétaire']].map(([role, label]) => <section key={role}><h4>{label} — non authentifié</h4>{(comptes[role] || []).map((item) => <article key={item.chunk_id}><blockquote>{item.text}</blockquote><small>{item.source} · {item.status}</small></article>)}{!comptes[role]?.length && <p>Aucune déclaration classée pour cette partie.</p>}</section>)}</div>
            </>}

            {onglet === 'recherche' && <>
              <h3>Rechercher ou poser une question factuelle</h3>
              <form className="dossiers-litige__recherche" onSubmit={rechercherPreuves}>
                <label htmlFor="question-litige">Question sur les documents</label><input id="question-litige" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} placeholder="Ex. Quel montant du loyer est écrit dans le bail ?" />
                <button className="bouton bouton--secondaire" disabled={chargement || !pieces.length}>Rechercher les passages</button>
                <button className="bouton bouton--principal" type="button" onClick={demanderReponse} disabled={chargement || !pieces.length || !question.trim()}>Obtenir une réponse sourcée</button>
              </form>
              {recherche?.items?.length > 0 && <ul className="dossiers-litige__sources">{recherche.items.map((p) => <li key={p.chunk_id}><header><strong>{p.nom_fichier} · {p.chunk_id}</strong><span>Score {p.score} · {recherche.mode}</span></header><blockquote>{p.texte}</blockquote></li>)}</ul>}
              {reponse && <section className="dossiers-litige__reponse" aria-live="polite"><h4>{reponse.answer_status}</h4><p>{reponse.answer}</p>{reponse.value && <p><strong>Valeur extraite : {reponse.value}</strong></p>}{reponse.citations?.map((citation) => { const doc = pieces.find((d) => d.passages?.some((p) => (p.chunk_id || p.id) === citation.chunk_id)); return <blockquote key={citation.chunk_id}><strong>{doc?.nom || 'Document'} · {citation.chunk_id}</strong><br />{citation.quote}</blockquote> })}<small>{AVERTISSEMENT}</small></section>}
              <p className="dossiers-litige__limite">Une réponse n’est construite qu’à partir de passages importés. Si la preuve manque, le système s’abstient.</p>
            </>}

            {onglet === 'rapport' && <>
              <h3>Exporter une synthèse pour revue humaine</h3>
              <div className="dossiers-litige__export">{['json', 'markdown', 'html', 'csv'].map((format) => <button key={format} className="bouton bouton--secondaire" type="button" disabled={chargement} onClick={() => genererRapport(format)}>Télécharger {format.toUpperCase()}</button>)}</div>
              <p>Les rapports incluent l’avertissement, les documents, les passages, la chronologie, les déclarations et les points de revue humaine.</p>
              <h4>Types non identifiés dans les documents importés</h4>
              {nonIdentifiees.map((item) => <span className="dossiers-litige__badge" key={item.evidence_type}>{item.evidence_type}</span>)}
              <p className="dossiers-litige__confidentialite">Un type non identifié n’est pas une preuve de non-existence.</p>
              <h4>Déclarations à comparer manuellement</h4>
              {contradictions.length ? contradictions.map((item, i) => <article className="dossiers-litige__source" key={`${item.issue}-${i}`}><strong>{item.issue} · à vérifier humainement</strong><p>Locataire : {item.tenant.quote}</p><p>Propriétaire : {item.landlord.quote}</p></article>) : <p>Aucune paire de déclarations des deux parties n’a été classée sur un même sujet.</p>}
            </>}

            {onglet === 'limites' && <>
              <h3>Configuration et limites</h3>
              <p>Mode de recherche : <strong>{configuration?.semantic_model_available ? 'hybride local avec modèle installé' : 'TF-IDF local'}</strong>. Aucun modèle n’est téléchargé automatiquement.</p>
              <ul>
                <li>Les documents importés sont des pièces non vérifiées et ne sont pas authentifiés par l’application.</li>
                <li>Les dates extraites sont des mentions trouvées dans les documents ; elles ne sont pas authentifiées.</li>
                <li>L’absence de résultat ne prouve pas l’absence d’une preuve dans le dossier.</li>
                <li>Aucun document privé n’est envoyé à un service externe ; le traitement et la recherche restent locaux.</li>
                {(configuration?.limits || []).map((limite) => <li key={limite}>{limite}</li>)}
                <li>Une preuve de paiement initial ne prouve pas un remboursement.</li>
              </ul>
              <p>{AVERTISSEMENT}</p>
            </>}
          </section>
        </section> : <section className="dossiers-litige__panneau dossiers-litige__vide">Créez ou sélectionnez un dossier pour commencer.</section>}
      </div>
    </main>
  )
}

