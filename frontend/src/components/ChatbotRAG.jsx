import { useEffect, useRef, useState } from 'react'
import { envoyerMessageRag, importerDocumentRag, obtenirChecklists, obtenirSuggestions } from '../api/rag'
import AnalyseurDocument from './AnalyseurDocument'

/**
 * Chatbot RAG bilingue pour les questions immobilières et l'import de PDF.
 * @param {object} props
 * @param {boolean} [props.modeFlottant] Affiche le widget minimisable.
 * @param {string} [props.transactionInitiale] Type initial : location ou vente.
 */
export default function ChatbotRAG({
  modeFlottant = false,
  transactionInitiale = 'location',
}) {
  const [ouvert, setOuvert] = useState(!modeFlottant)
  const [langue, setLangue] = useState('fr')
  const [transaction, setTransaction] = useState(transactionInitiale)
  const [modalOutil, setModalOutil] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [checklists, setChecklists] = useState(null)
  const [checklistOuverte, setChecklistOuverte] = useState(false)
  const [elementsCoches, setElementsCoches] = useState({})
  const [messageSaisi, setMessageSaisi] = useState('')
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [importEnCours, setImportEnCours] = useState(false)

  const messagesFinRef = useRef(null)
  const fichierPdfRef = useRef(null)

  async function importerPdfDansAssistant(event) {
    const fichier = event.target.files?.[0]
    event.target.value = ''
    if (!fichier) return
    if (!fichier.name.toLowerCase().endsWith('.pdf')) {
      setErreur('Choisissez un fichier PDF.')
      return
    }
    if (fichier.size > 5 * 1024 * 1024) {
      setErreur('Le PDF ne doit pas d?passer 5 Mo.')
      return
    }

    setErreur(null)
    setImportEnCours(true)
    try {
      const resultat = await importerDocumentRag(fichier)
      setMessages((anciens) => [
        ...anciens,
        {
          role: 'assistant',
          texte: `PDF « ${resultat.nom} » ajouté à vos documents. ${resultat.pages} page(s) et ${resultat.passages} passages indexés. Vous pouvez maintenant poser une question sur ce fichier.`,
        },
      ])
      const suggestionsPdf = await obtenirSuggestions(langue, transaction).catch(() => null)
      if (suggestionsPdf) setSuggestions(suggestionsPdf)
    } catch (erreurImport) {
      console.error('Échec de l’importation RAG:', erreurImport.response?.data || erreurImport.message)
      setErreur(
        erreurImport.response?.data?.message ||
          erreurImport.response?.data?.msg ||
          (erreurImport.response?.status === 401
            ? 'Votre session a expiré. Reconnectez-vous, puis ajoutez le PDF.'
            : erreurImport.response?.status === 413
              ? 'Le PDF dépasse la limite autorisée de 5 Mo.'
              : erreurImport.response
                ? `Le serveur a refusé l’import (HTTP ${erreurImport.response.status}). Consultez son terminal pour le détail.`
                : 'Le serveur Flask ne répond pas. Vérifiez qu’il est démarré et réessayez.'),
      )
    } finally {
      setImportEnCours(false)
    }
  }

  // Message d'accueil selon la langue
  const messageAccueil = {
    fr: {
      role: 'assistant',
      texte:
        '👋 Bonjour ! Je suis votre **assistant documentaire immobilier pour la Tunisie**.\n\n' +
        'Je peux vous guider sur les **pièces obligatoires**, les **démarches administratives** (municipalité, recette des finances, conservation foncière CPF) et les formalités pour les **étudiants** (caution solidaire, garant).\n\n' +
        'Choisissez Location ou Vente, puis posez-moi votre question.',
      sources: [
        { titre: 'Législation immobilière tunisienne', source: 'Code des Obligations et des Contrats & Code des Droits Réels' },
      ],
    },
    ar: {
      role: 'assistant',
      texte:
        '👋 مرحباً بكم ! أنا **مساعدكم القانوني والإجرائي للعقارات في تونس**.\n\n' +
        'أساعدكم في معرفة **الوثائق الإلزامية**، و**الإجراءات الإدارية** (التعريف بالإمضاء بالبلدية، التسجيل بالقباضة المالية، وإدارة الملكية العقارية)، مع إرشادات خاصة **بالطلبة والجامعيين** (الضمان التضامني والكراء المشترك).\n\n' +
        '\u0627\u062e\u062a\u0631 \u0646\u0648\u0639 \u0627\u0644\u0645\u0639\u0627\u0645\u0644\u0629 \u0648\u0627\u0637\u0631\u062d \u0633\u0624\u0627\u0644\u0643 \u0645\u0628\u0627\u0634\u0631\u0629 !',
      sources: [
        { titre: 'التشريع العقاري التونسي', source: 'مجلة الالتزامات والعقود ومجلة الحقوق العينية (الفصل 377 مكرر)' },
      ],
    },
  }

  const [messages, setMessages] = useState([messageAccueil.fr])

  // Recharge les questions personnalisées à l'ouverture, pour retrouver les PDF de la session.
  useEffect(() => {
    if (!ouvert) return undefined
    let ignore = false
    obtenirSuggestions(langue, transaction)
      .then((donnees) => {
        if (!ignore) setSuggestions(donnees || [])
      })
      .catch(() => {})
    return () => { ignore = true }
  }, [langue, transaction, ouvert])

  // Chargement de la checklist
  useEffect(() => {
    let ignore = false
    obtenirChecklists(transaction)
      .then((donnees) => {
        if (!ignore) setChecklists(donnees)
      })
      .catch(() => {})
    return () => { ignore = true }
  }, [transaction])

  // Défilement automatique vers le bas à chaque nouveau message
  useEffect(() => {
    if (ouvert && typeof messagesFinRef.current?.scrollIntoView === 'function') {
      messagesFinRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, ouvert])

  // Changement de langue
  function changerLangue(nouvelleLangue) {
    setLangue(nouvelleLangue)
    setMessages([messageAccueil[nouvelleLangue]])
  }

  // Envoi d'un message
  async function envoyer(texteAEnvoyer) {
    const texte = (texteAEnvoyer || messageSaisi).trim()
    if (!texte || envoiEnCours) return

    setErreur(null)
    setMessageSaisi('')

    const nouveauMessageUtilisateur = {
      role: 'user',
      texte,
    }

    setMessages((anciens) => [...anciens, nouveauMessageUtilisateur])
    setEnvoiEnCours(true)

    try {
      const reponse = await envoyerMessageRag({
        message: texte,
        transaction,
        langue,
      })

      const nouveauMessageAssistant = {
        role: 'assistant',
        texte: reponse.reponse,
        sources: reponse.sources || [],
        audit: reponse.audit,
      }

      setMessages((anciens) => [...anciens, nouveauMessageAssistant])
    } catch (erreurRequete) {
      setErreur(
        erreurRequete.response?.data?.message ||
          (langue === 'ar'
            ? '\u0639\u0630\u0631\u0627\u060b\u060c \u062d\u062f\u062b \u062e\u0637\u0623 \u0623\u062b\u0646\u0627\u0621 \u0645\u0639\u0627\u0644\u062c\u0629 \u0627\u0644\u0633\u0624\u0627\u0644. \u0627\u0644\u0631\u062c\u0627\u0621 \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629 \u0645\u062c\u062f\u062f\u0627\u064b.'
            : "Une erreur est survenue lors de l'analyse. Reessayez apres avoir verifie le serveur."),
      )
    } finally {
      setEnvoiEnCours(false)
    }
  }

  const estArabe = langue === 'ar'

  if (modeFlottant && !ouvert) {
    return (
      <button
        type="button"
        className="chatbot-flottant-declencheur"
        onClick={() => setOuvert(true)}
        aria-label="Ouvrir l'assistant immobilier IA"
      >
        IA
      </button>
    )
  }

  return (
    <div
      className={`chatbot-rag ${modeFlottant ? 'chatbot-rag--flottant' : ''} ${
        estArabe ? 'chatbot-rag--rtl' : ''
      }`}
      dir={estArabe ? 'rtl' : 'ltr'}
    >
      {/* En-tête du Chatbot */}
      <div className="chatbot-rag__entete">
        <div className="chatbot-rag__titre-groupe">
          <span className="chatbot-rag__badge-ia">RAG IA</span>
          <h3 className="chatbot-rag__titre">
            {estArabe ? 'مساعد الوثائق العقارية' : 'Assistant Documents & Démarches'}
          </h3>
        </div>

        <div className="chatbot-rag__actions-entete">
          {/* Bascule de langue */}
          <div className="chatbot-rag__langue-switch">
            <button
              type="button"
              className={`chatbot-rag__btn-langue ${langue === 'fr' ? 'actif' : ''}`}
              onClick={() => changerLangue('fr')}
              title="Passer en français"
            >
              FR
            </button>
            <button
              type="button"
              className={`chatbot-rag__btn-langue ${langue === 'ar' ? 'actif' : ''}`}
              onClick={() => changerLangue('ar')}
              title="التحويل إلى العربية"
            >
              عربي
            </button>
          </div>

          {modeFlottant && (
            <button
              type="button"
              className="chatbot-rag__btn-fermer"
              onClick={() => setOuvert(false)}
              aria-label="Fermer le chatbot"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Choix du type de transaction */}
      <div className="chatbot-rag__controles">
        <div className="chatbot-rag__onglets-transaction">
          <button
            type="button"
            className={`chatbot-rag__onglet ${transaction === 'location' ? 'actif' : ''}`}
            onClick={() => setTransaction('location')}
          >
            {estArabe ? '\u0643\u0631\u0627\u0621' : 'Location'}
          </button>
          <button
            type="button"
            className={`chatbot-rag__onglet ${transaction === 'vente' ? 'actif' : ''}`}
            onClick={() => setTransaction('vente')}
          >
            {estArabe ? '\u0628\u064a\u0639' : 'Vente'}
          </button>
        </div>

      </div>

      {/* Barre d'outils rapides : OCR Document & Générateur de contrat */}
      <div className="chatbot-rag__outils-rapides">
        <input
          ref={fichierPdfRef}
          className="documents-rag__fichier"
          type="file"
          accept="application/pdf,.pdf"
          onChange={importerPdfDansAssistant}
          aria-label="Choisir un PDF à ajouter à l’assistant"
        />
        <button
          type="button"
          className="chatbot-rag__btn-outil"
          onClick={() => fichierPdfRef.current?.click()}
          disabled={importEnCours}
        >
          <span>📎</span>
          <span>{importEnCours ? 'Indexation…' : estArabe ? 'إضافة PDF' : 'Ajouter un PDF'}</span>
        </button>
        <button
          type="button"
          className="chatbot-rag__btn-outil"
          onClick={() => setModalOutil('ocr')}
        >
          <span>📄</span>
          <span>{estArabe ? 'فحص عقد PDF (OCR)' : 'Analyser un contrat PDF (OCR)'}</span>
        </button>
        <button
          type="button"
          className="chatbot-rag__btn-outil"
          onClick={() => setChecklistOuverte((o) => !o)}
        >
          <span>📋</span>
          <span>{estArabe ? 'قائمة الوثائق' : 'Checklist interactive'}</span>
        </button>
      </div>

      {/* Panneau de checklist interactive */}
      {checklistOuverte && (checklists?.[transaction] || checklists) && (
        <div className="chatbot-rag__checklist-panneau" aria-label="Checklist">
          <ul className="chatbot-rag__checklist-liste">
            {((checklists[transaction] && checklists[transaction].elements) || checklists.elements || []).map((elem) => (
              <li key={elem.id} className="chatbot-rag__checklist-item">
                <label className="chatbot-rag__checklist-label">
                  <input
                    type="checkbox"
                    checked={Boolean(elementsCoches[elem.id])}
                    onChange={(e) =>
                      setElementsCoches((prev) => ({ ...prev, [elem.id]: e.target.checked }))
                    }
                  />
                  <span>{estArabe ? elem.nom_ar : elem.nom_fr}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Zone d'affichage des messages */}
      <div className="chatbot-rag__corps-messages">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`chatbot-rag__message chatbot-rag__message--${msg.role}`}
          >
            <div className="chatbot-rag__bulle">
              <div className="chatbot-rag__texte-markdown">
                {msg.texte.split('\n\n').map((paragraphe, pIdx) => (
                  <p key={pIdx}>
                    {paragraphe.split('\n').map((ligne, lIdx) => (
                      <span key={lIdx}>
                        {ligne}
                        <br />
                      </span>
                    ))}
                  </p>
                ))}
              </div>

              {/* Citations de sources officielles */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="chatbot-rag__sources">
                  <span className="chatbot-rag__sources-titre">
                    {estArabe ? '📚 المصادر القانونية المعتمدة :' : '📚 Sources juridiques citées :'}
                  </span>
                  <ul>
                    {msg.sources.map((src, sIdx) => (
                      <li key={sIdx}>
                        <strong>{src.titre}</strong> — <em>{src.source}</em>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}

        {envoiEnCours && (
          <div className="chatbot-rag__message chatbot-rag__message--assistant">
            <div className="chatbot-rag__bulle chatbot-rag__bulle--chargement">
              <span className="chatbot-rag__points-chargement">
                {estArabe ? 'جاري تحليل الوثائق والبحث في النصوص القانونية...' : 'Analyse de votre demande et consultation des textes légaux...'}
              </span>
            </div>
          </div>
        )}

        {erreur && <div className="alerte alerte--erreur">{erreur}</div>}
        <div ref={messagesFinRef} />
      </div>

      {/* Suggestions rapides cliquables */}
      {suggestions.length > 0 && (
        <div className="chatbot-rag__suggestions">
          <span className="chatbot-rag__suggestions-label">
            {suggestions.some((suggestion) => suggestion.source === 'pdf')
              ? estArabe ? '💡 أسئلة مقترحة من ملفات PDF :' : '💡 Questions tirées de vos PDF :'
              : estArabe ? '💡 أسئلة شائعة :' : '💡 Questions fréquentes :'}
          </span>
          <div className="chatbot-rag__suggestions-liste">
            {suggestions
              .filter((s) => s.transaction === transaction || transaction === 'general')
              .slice(0, 3)
              .map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="chatbot-rag__chip"
                  onClick={() => envoyer(s.question)}
                  disabled={envoiEnCours}
                >
                  {s.titre}
                </button>
              ))}
          </div>
        </div>
      )}

      {/* Formulaire de saisie */}
      <form
        className="chatbot-rag__formulaire"
        onSubmit={(e) => {
          e.preventDefault()
          envoyer()
        }}
      >
        <input
          type="text"
          className="chatbot-rag__champ-saisie"
          placeholder={
            estArabe
              ? 'اطرح سؤالك هنا حول الوثائق أو الإجراءات...'
              : 'Posez votre question sur les pièces, délais, démarches...'
          }
          value={messageSaisi}
          onChange={(e) => setMessageSaisi(e.target.value)}
          disabled={envoiEnCours}
        />
        <button
          type="submit"
          className="bouton bouton--principal chatbot-rag__btn-envoyer"
          disabled={!messageSaisi.trim() || envoiEnCours}
        >
          {estArabe ? 'إرسال' : 'Envoyer'}
        </button>
      </form>

      {/* Modal d'outils (OCR ou Générateur de contrat) */}
      {modalOutil && (
        <div className="chatbot-rag__modal-overlay" role="dialog" aria-modal="true">
          <div className="chatbot-rag__modal-contenu">
            <button
              type="button"
              className="chatbot-rag__modal-fermer"
              onClick={() => setModalOutil(null)}
              aria-label="Fermer la boîte de dialogue"
            >
              ✕
            </button>
              <AnalyseurDocument
                transactionInitiale={transaction}
                langue={langue}

              />
          </div>
        </div>
      )}
    </div>
  )
}
