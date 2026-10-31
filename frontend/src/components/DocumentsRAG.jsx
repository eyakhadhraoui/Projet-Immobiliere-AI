import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { importerDocumentRag, listerDocumentsRag, supprimerDocumentRag } from '../api/rag'
import { useAuth } from '../hooks/useAuth'
import { useRequete } from '../hooks/useRequete'

export default function DocumentsRAG() {
  const { utilisateur } = useAuth()
  const [importEnCours, setImportEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [message, setMessage] = useState('')
  const fichierRef = useRef(null)
  const { donnees, etat, erreur: erreurChargement, reessayer, modifierDonnees } = useRequete('documents-rag', listerDocumentsRag)
  const documents = donnees || []

  async function importer(event) {
    const fichier = event.target.files?.[0]
    event.target.value = ''
    if (!fichier) return
    if (!fichier.name.toLowerCase().endsWith('.pdf')) {
      setErreur('Choisissez un fichier PDF.')
      return
    }
    setImportEnCours(true)
    setErreur('')
    setMessage('Extraction du texte et indexation sémantique en cours… Le premier import peut télécharger le modèle multilingue.')
    try {
      const resultat = await importerDocumentRag(fichier)
      setMessage(`${resultat.nom} est indexé : ${resultat.pages} page(s), ${resultat.passages} passages. Le document est privé à votre compte.`)
      reessayer()
    } catch (e) {
      setMessage('')
      setErreur(e.response?.data?.message || 'Échec de l’indexation du PDF.')
    } finally {
      setImportEnCours(false)
    }
  }

  async function supprimer(document) {
    if (!window.confirm(`Supprimer « ${document.nom} » de vos documents RAG ?`)) return
    setErreur('')
    try {
      await supprimerDocumentRag(document.id)
      modifierDonnees((liste) => (liste || []).filter((element) => element.id !== document.id))
      setMessage(`${document.nom} a été supprimé de votre bibliothèque.`)
    } catch (e) {
      setErreur(e.response?.data?.message || 'Impossible de supprimer ce document.')
    }
  }

  return (
    <section className="documents-rag" aria-labelledby="documents-rag-titre">
      <header className="documents-rag__entete">
        <div>
          <span className="badge badge--principal">Base documentaire RAG</span>
          <h2 id="documents-rag-titre">Documents de référence</h2>
          <p>Importez des PDF pour qu’ils soient découpés en passages, indexés et cités par l’assistant dans ses réponses.</p>
        </div>
        {utilisateur ? (
          <>
            <input ref={fichierRef} className="documents-rag__fichier" type="file" accept="application/pdf,.pdf" onChange={importer} />
            <button type="button" className="bouton bouton--principal" onClick={() => fichierRef.current?.click()} disabled={importEnCours}>
              {importEnCours ? 'Indexation…' : 'Importer un PDF'}
            </button>
          </>
        ) : <Link className="bouton bouton--principal" to="/connexion">Connectez-vous pour importer</Link>}
      </header>

      {message && <p className="documents-rag__message" role="status">{message}</p>}
      {(erreur || erreurChargement?.message) && <p className="documents-rag__erreur" role="alert">{erreur || erreurChargement.message}</p>}

      {etat === 'chargement' ? <p className="etat" role="status">Chargement et préparation de la base documentaire…</p> : documents.length ? (
        <ul className="documents-rag__liste">
          {documents.map((document) => (
            <li className="documents-rag__item" key={document.id}>
              <span className="documents-rag__icone" aria-hidden="true">PDF</span>
              <div className="documents-rag__details">
                <strong>{document.nom}</strong>
                <span>{document.type === 'guide' ? 'Guide fourni au projet' : document.type === 'reference' ? 'Corpus de référence' : 'Document privé'} · {document.pages || '—'} page(s) · {document.passages} passage(s){document.ocr ? ' · OCR effectué' : ''}</span>
              </div>
              {!document.supprimable && <span className="documents-rag__badge">Source partagée</span>}
              {document.supprimable && <button type="button" className="bouton bouton--secondaire" onClick={() => supprimer(document)}>Supprimer</button>}
            </li>
          ))}
        </ul>
      ) : <div className="documents-rag__vide">Aucun PDF indexé pour le moment.</div>}

      <p className="documents-rag__confidentialite">Les PDF importés sont associés à votre compte. Le guide fourni avec le projet et les références générales restent accessibles à tous.</p>
    </section>
  )
}
