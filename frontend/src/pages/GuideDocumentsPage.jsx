import { useState } from 'react'
import ChatbotRAG from '../components/ChatbotRAG'
import AnalyseurDocument from '../components/AnalyseurDocument'
import GenerateurContrat from '../components/GenerateurContrat'
import DocumentsRAG from '../components/DocumentsRAG'

/**
 * Page dédiée au Guide documentaire et légal de l'immobilier en Tunisie.
 * Intègre le Guide pratique officiel (Diwan & Conservation Foncière),
 * le Chatbot RAG interactif bilingue,
 * l'analyseur OCR de documents/contrats et le générateur de contrats types.
 */
export default function GuideDocumentsPage() {
  const transactionInitiale = 'location'
  const [ongletActif, setOngletActif] = useState('chatbot') // 'chatbot' | 'documents' | 'ocr' | 'contrat'

  const lignesTableau = [
    {
      element: 'Identité des parties',
      location: 'À préparer',
      vente: 'À préparer',
      etat: 'Présent / Manquant',
      badge: 'obligatoire',
    },
    {
      element: 'Justificatif de propriété / droit de louer',
      location: 'À vérifier',
      vente: 'À vérifier',
      etat: 'Présent / Manquant',
      badge: 'obligatoire',
    },
    {
      element: 'Contrat ou projet d’acte',
      location: 'Contrat de location',
      vente: 'Acte de vente (Art. 377 bis)',
      etat: 'Présent / Manquant',
      badge: 'obligatoire',
    },
    {
      element: 'Description et références du bien',
      location: 'À renseigner',
      vente: 'À renseigner',
      etat: 'Présent / Manquant',
      badge: 'obligatoire',
    },
    {
      element: 'Pièces fiscales / reçus',
      location: 'Selon formalités (1 %)',
      vente: 'Selon formalités (Quitus)',
      etat: 'Présent / À confirmer',
      badge: 'confirmation',
    },
    {
      element: 'Annexes et documents complémentaires',
      location: 'Selon le contrat (état lieux)',
      vente: 'Selon le dossier (syndic)',
      etat: 'Présent / À confirmer',
      badge: 'confirmation',
    },
    {
      element: 'Signatures, enregistrement et formalités foncières',
      location: 'À vérifier (Baladiya)',
      vente: 'À vérifier (CPF)',
      etat: 'Fait / À faire',
      badge: 'action',
    },
  ]

  return (
    <div className="page-guide-documents conteneur">
      {/* Bannière et Avertissement officiel */}
      <header className="page-guide-documents__banniere">
        <span className="badge badge--principal">Guide Pratique • Tunisie</span>
        <h1 className="page-guide-documents__titre">
          Documents nécessaires pour la location et la vente immobilière
        </h1>
        <p className="page-guide-documents__chapeau">
          Liste indicative des pièces, justificatifs et démarches pour préparer votre dossier et repérer les pièces à vérifier avant de finaliser une transaction.
        </p>

        <div className="alerte alerte--info" role="note" style={{ textAlign: 'left', marginTop: '1rem' }}>
          <strong>À quoi sert ce guide ?</strong> Ce document aide un propriétaire, un locataire, un acheteur ou un vendeur à préparer son dossier immobilier et à repérer les pièces à vérifier avant de finaliser une transaction.
          <br />
          <em>Important :</em> la liste exacte dépend du type de bien, de la situation des parties, de la nature de l’opération et des formalités applicables. Ce guide est informatif et ne remplace pas la confirmation auprès de la Recette des finances, de la Conservation de la propriété foncière, d’un notaire, d’un avocat ou du professionnel compétent.
        </div>
      </header>

      {/* Barre d'onglets principaux : Assistant RAG, OCR Document, Générateur */}
      <nav className="page-guide-documents__onglets-principaux" aria-label="Outils du guide">
        <button
          type="button"
          className={`page-guide-documents__tab-btn ${ongletActif === 'documents' ? 'actif' : ''}`}
          onClick={() => setOngletActif('documents')}
        >
          <span>📚</span>
          <span>Documents RAG</span>
        </button>
        <button
          type="button"
          className={`page-guide-documents__tab-btn ${ongletActif === 'chatbot' ? 'actif' : ''}`}
          onClick={() => setOngletActif('chatbot')}
        >
          <span>💬</span>
          <span>Assistant Documents & IA</span>
        </button>
        <button
          type="button"
          className={`page-guide-documents__tab-btn ${ongletActif === 'ocr' ? 'actif' : ''}`}
          onClick={() => setOngletActif('ocr')}
        >
          <span>📄</span>
          <span>OCR & Analyse de Contrat (PDF)</span>
        </button>
        <button
          type="button"
          className={`page-guide-documents__tab-btn ${ongletActif === 'contrat' ? 'actif' : ''}`}
          onClick={() => setOngletActif('contrat')}
        >
          <span>✍️</span>
          <span>Générateur de Contrat Type</span>
        </button>
      </nav>

      {/* Grille principale : Outil interactif à gauche & Tableau / Guides à droite */}
      <div className="page-guide-documents__grille">
        {/* Colonne gauche : Outil sélectionné */}
        <section className="page-guide-documents__col-chatbot" aria-label="Outil interactif sélectionné">
          {ongletActif === 'chatbot' && (
            <ChatbotRAG
              modeFlottant={false}
              transactionInitiale={transactionInitiale}
            />
          )}
          {ongletActif === 'ocr' && (
            <AnalyseurDocument
              transactionInitiale={transactionInitiale}
            />
          )}
          {ongletActif === 'documents' && <DocumentsRAG />}
          {ongletActif === 'contrat' && (
            <GenerateurContrat typeInitial={transactionInitiale} />
          )}
        </section>

        {/* Colonne droite : Synthèse explicative des organismes et formalités */}
        <aside className="page-guide-documents__col-info" aria-label="Démarches et conseils pratiques">
          {/* Les 5 démarches générales */}
          <div className="carte-info-juridique">
            <h2 className="carte-info-juridique__titre">🏛️ Les 5 démarches générales (Tunisie)</h2>

            <div className="etapes-liste">
              <div className="etape-item">
                <span className="etape-item__num">1</span>
                <div>
                  <strong>Vérifier l’identité et la capacité</strong>
                  <p>Vérifier l’identité des parties et le droit du bailleur/vendeur à disposer du bien (titre foncier ou mandat).</p>
                </div>
              </div>

              <div className="etape-item">
                <span className="etape-item__num">2</span>
                <div>
                  <strong>Préparer le contrat / projet d’acte</strong>
                  <p>Vérifier la cohérence des informations (adresse, prix, charges, modalités de paiement et résiliation).</p>
                </div>
              </div>

              <div className="etape-item">
                <span className="etape-item__num">3</span>
                <div>
                  <strong>Légalisation municipale (Baladiya - التعريف بالإمضاء)</strong>
                  <p>Légalisation obligatoire des signatures pour les baux d’habitation et promesses de vente.</p>
                </div>
              </div>

              <div className="etape-item">
                <span className="etape-item__num">4</span>
                <div>
                  <strong>Enregistrement à la Recette des finances (القباضة المالية)</strong>
                  <p>Consulter les exigences de la Recette compétente (copies du contrat, justificatifs fiscaux, délai de 60 jours).</p>
                </div>
              </div>

              <div className="etape-item">
                <span className="etape-item__num">5</span>
                <div>
                  <strong>Conservation foncière (CPF) & Conservation des reçus</strong>
                  <p>Formalités d’inscription au registre foncier pour les ventes et conservation des reçus officiels délivrés.</p>
                </div>
              </div>
            </div>
          </div>

          {/* Spécial étudiants */}
          <div className="carte-info-juridique carte-info-juridique--etudiant">
            <h2 className="carte-info-juridique__titre">🎓 Spécial Étudiants & Colocation</h2>
            <p>Pour louer sereinement près de votre université :</p>
            <ul>
              <li><strong>Caution solidaire :</strong> Engagement légalisé de vos parents/tuteur + fiche de paie récente.</li>
              <li><strong>État des lieux contradictoire :</strong> Dressé à l’entrée et à la sortie pour récupérer la caution (1 à 2 mois).</li>
              <li><strong>Colocation :</strong> Mention de tous les colocataires sur le bail avec clause de solidarité.</li>
            </ul>
          </div>
        </aside>
      </div>

      {/* Section pleine largeur : Tableau de contrôle du dossier */}
      <section className="section-tableau-controle" style={{ marginTop: '2.5rem' }}>
        <h2 className="section-tableau-controle__titre">
          3. Tableau de contrôle du dossier
        </h2>
        <p className="texte-doux" style={{ marginBottom: '1rem' }}>
          Utilisez ce tableau avant de considérer le dossier comme prêt. « À confirmer » signifie que l’exigence doit être vérifiée selon le cas et auprès de l’autorité ou du professionnel compétent.
        </p>

        <div className="tableau-defilement">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Élément</th>
                <th scope="col">Location</th>
                <th scope="col">Vente</th>
                <th scope="col">État à vérifier</th>
              </tr>
            </thead>
            <tbody>
              {lignesTableau.map((ligne, idx) => (
                <tr key={idx}>
                  <td><strong>{ligne.element}</strong></td>
                  <td>{ligne.location}</td>
                  <td>{ligne.vente}</td>
                  <td>
                    <span className={`badge ${
                      ligne.badge === 'obligatoire'
                        ? 'badge--rouge'
                        : ligne.badge === 'confirmation'
                          ? 'badge--jaune'
                          : 'badge--bleu'
                    }`}>
                      {ligne.etat}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Section Conseils pour vérifier les pages d'un contrat */}
      <section className="section-conseils-contrat" style={{ marginTop: '2.5rem' }}>
        <div className="carte-info-juridique" style={{ background: 'var(--surface)' }}>
          <h2 className="carte-info-juridique__titre">
            4. Conseils pour vérifier les pages d’un contrat
          </h2>
          <ul style={{ lineHeight: '1.7', fontSize: '0.95rem' }}>
            <li><strong>Comparer le nombre de pages</strong> du fichier avec la numérotation visible sur les pages (ex. 1/4, 2/4...).</li>
            <li><strong>Repérer les sauts de numérotation</strong>, les pages vides ou les pages illisibles.</li>
            <li><strong>Vérifier les annexes :</strong> s’assurer que tout document mentionné dans le contrat est effectivement joint au dossier.</li>
            <li><strong>Ne pas conclure hâtivement</strong> qu’une page est juridiquement manquante sur la seule base d’un saut de numéro : demander confirmation à l’émetteur ou au professionnel chargé du dossier.</li>
            <li><strong>Distinguer clairement :</strong> une pièce non fournie, une pièce illisible et une pièce dont l’obligation reste à confirmer.</li>
          </ul>
        </div>
      </section>

      {/* Section Sources et Liens officiels */}
      <footer className="section-sources-guide" style={{ marginTop: '2rem', padding: '1.5rem', background: 'var(--fond)', borderRadius: '8px' }}>
        <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.5rem 0' }}>5. Sources officielles consultées</h3>
        <ul style={{ fontSize: '0.9rem', margin: 0, paddingLeft: '1.25rem', lineHeight: '1.6' }}>
          <li>
            Diwan — <em>Enregistrement d’un contrat de location :</em>{' '}
            <a href="https://www.diwan.tn/fr/article/article_location" target="_blank" rel="noreferrer">
              https://www.diwan.tn/fr/article/article_location
            </a>
          </li>
          <li>
            Diwan — <em>Enregistrement d’un acte d’acquisition d’un bien immobilier :</em>{' '}
            <a href="https://www.diwan.tn/fr/article/cession" target="_blank" rel="noreferrer">
              https://www.diwan.tn/fr/article/cession
            </a>
          </li>
          <li>
            Portail national des services administratifs — <em>Affaires foncières :</em>{' '}
            <a href="https://services.gov.tn/affaires-foncieres/" target="_blank" rel="noreferrer">
              https://services.gov.tn/affaires-foncieres/
            </a>
          </li>
        </ul>
        <p className="texte-doux" style={{ fontSize: '0.8rem', marginTop: '0.75rem', marginBottom: 0 }}>
          Les procédures, formulaires, taxes et pièces exigées peuvent changer. Avant de signer ou de déposer un dossier, confirmez les exigences actualisées auprès des services tunisiens compétents ou d’un professionnel qualifié.
        </p>
      </footer>
    </div>
  )
}
