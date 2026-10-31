import { useState } from 'react'
import { analyserDocument } from '../api/rag'

/**
 * Composant d'analyse documentaire, OCR et vérification de complétude.
 * Permet d'importer un contrat PDF ou du texte, d'extraire les métadonnées,
 * de détecter les sauts de page, les champs vides et de vérifier la checklist.
 *
 * @param {object} props
 * @param {string} [props.transactionInitiale] 'location' ou 'vente'.
 * @param {string} [props.langue] 'fr' ou 'ar'.
 * @param {Function} [props.onChecklistMiseAJour] Callback appelée avec les éléments détectés.
 */
export default function AnalyseurDocument({
  transactionInitiale = 'location',
  langue = 'fr',
  onChecklistMiseAJour,
}) {
  const [transaction, setTransaction] = useState(transactionInitiale)
  const [fichier, setFichier] = useState(null)
  const [texteSaisi, setTexteSaisi] = useState('')
  const [modeSaisie, setModeSaisie] = useState('fichier') // 'fichier' ou 'texte'
  const [chargement, setChargement] = useState(false)
  const [rapport, setRapport] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [glisserActif, setGlisserActif] = useState(false)

  const estArabe = langue === 'ar'

  // Exemple de test rapide avec des anomalies pour démonstration
  const exempleContratLocation = `CONTRAT DE LOCATION D'HABITATION
Entre M. Mohamed Ben Salem, CIN n° 08765432, Propriétaire
Et Mlle Nour Trabelsi, CIN n° 11223344, Locataire étudiante

Page 1 sur 3
Le bailleur donne en location un appartement S+2 sis à Ennasr 2, Ariana.
Loyer mensuel : 850 DT. Caution : 850 DT.
Durée du bail : ................. (à compléter)
Le preneur s'engage à respecter l'état des lieux (Annexe 1).

Page 3 sur 3
Fait à Tunis, le 15/09/2026.
Signatures des parties avec légalisation municipale (Baladiya).
Bailleur: Lu et approuvé [Signature]
Preneur: Lu et approuvé [Signature]`

  async function lancerAnalyse() {
    setErreur(null)
    setRapport(null)
    setChargement(true)

    try {
      let resultat
      if (modeSaisie === 'fichier') {
        if (!fichier) {
          setErreur(estArabe ? 'الرجاء اختيار ملف PDF للتحليل.' : 'Veuillez sélectionner un fichier PDF.')
          setChargement(false)
          return
        }
        const formData = new FormData()
        formData.append('fichier', fichier)
        formData.append('transaction', transaction)
        formData.append('langue', langue)
        resultat = await analyserDocument(formData)
      } else {
        if (!texteSaisi.trim()) {
          setErreur(estArabe ? 'الرجاء كتابة أو لصق نص العقد.' : 'Veuillez coller le texte du document à analyser.')
          setChargement(false)
          return
        }
        resultat = await analyserDocument({
          texte: texteSaisi,
          transaction,
          langue,
        })
      }

      setRapport(resultat)

      // Notifier le parent pour synchroniser la checklist si demandé
      if (onChecklistMiseAJour && resultat?.audit_checklist?.elements_fournis) {
        onChecklistMiseAJour(resultat.audit_checklist.elements_fournis, transaction)
      }
    } catch (err) {
      setErreur(
        err?.response?.data?.message ||
          (estArabe
            ? 'حدث خطأ أثناء معالجة المستند. الرجاء التأكد من الملف.'
            : "Une erreur est survenue lors de l'analyse du document."),
      )
    } finally {
      setChargement(false)
    }
  }

  function handleFileDrop(e) {
    e.preventDefault()
    setGlisserActif(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0]
      if (f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')) {
        setFichier(f)
        setModeSaisie('fichier')
      } else {
        setErreur(estArabe ? 'يجب أن يكون الملف بصيغة PDF.' : 'Seuls les fichiers PDF sont acceptés pour le moment.')
      }
    }
  }

  return (
    <div className={`analyseur-document ${estArabe ? 'analyseur-document--rtl' : ''}`} dir={estArabe ? 'rtl' : 'ltr'}>
      <div className="analyseur-document__entete">
        <div className="analyseur-document__titre-groupe">
          <span className="badge badge--principal">OCR & Analyseur</span>
          <h3 className="analyseur-document__titre">
            {estArabe ? 'فحص العقود والوثائق الرسمية بالذكاء الاصطناعي' : 'Analyse et audit documentaire de vos contrats'}
          </h3>
        </div>
        <p className="analyseur-document__sous-titre">
          {estArabe
            ? 'قم برفع عقد الكراء، وعد البيع أو المستندات الممسوحة ضوئياً للتثبت من اكتمال الصفحات، والبيانات الإلزامية، والحقول الناقصة.'
            : 'Téléversez un contrat PDF ou collez son texte pour détecter les pages manquantes, vérifier les signatures, les CIN et la complétude du dossier.'}
        </p>
      </div>

      {/* Choix de la transaction et du mode de saisie */}
      <div className="analyseur-document__barre-options">
        <div className="analyseur-document__onglets">
          <button
            type="button"
            className={`analyseur-document__onglet ${transaction === 'location' ? 'actif' : ''}`}
            onClick={() => setTransaction('location')}
          >
            {estArabe ? '🔑 كراء' : '🔑 Location'}
          </button>
          <button
            type="button"
            className={`analyseur-document__onglet ${transaction === 'vente' ? 'actif' : ''}`}
            onClick={() => setTransaction('vente')}
          >
            {estArabe ? '🏛️ بيع' : '🏛️ Vente'}
          </button>
        </div>

        <div className="analyseur-document__modes">
          <button
            type="button"
            className={`analyseur-document__btn-mode ${modeSaisie === 'fichier' ? 'actif' : ''}`}
            onClick={() => setModeSaisie('fichier')}
          >
            {estArabe ? '📄 ملف PDF' : '📄 Fichier PDF'}
          </button>
          <button
            type="button"
            className={`analyseur-document__btn-mode ${modeSaisie === 'texte' ? 'actif' : ''}`}
            onClick={() => setModeSaisie('texte')}
          >
            {estArabe ? '✏️ نص العقد' : '✏️ Texte du contrat'}
          </button>
        </div>
      </div>

      {/* Zone de dépôt ou saisie */}
      {modeSaisie === 'fichier' ? (
        <div
          className={`analyseur-document__dropzone ${glisserActif ? 'glisser' : ''} ${fichier ? 'avec-fichier' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setGlisserActif(true)
          }}
          onDragLeave={() => setGlisserActif(false)}
          onDrop={handleFileDrop}
        >
          <input
            id="input-fichier-pdf"
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => e.target.files && setFichier(e.target.files[0])}
            style={{ display: 'none' }}
          />
          <div className="analyseur-document__dropzone-icone">📑</div>
          {fichier ? (
            <div className="analyseur-document__fichier-info">
              <strong>{fichier.name}</strong>
              <span>({Math.round(fichier.size / 1024)} Ko)</span>
              <button
                type="button"
                className="bouton bouton--neutre bouton--compact"
                onClick={() => setFichier(null)}
              >
                {estArabe ? 'إلغاء' : 'Changer'}
              </button>
            </div>
          ) : (
            <div className="analyseur-document__dropzone-consigne">
              <label htmlFor="input-fichier-pdf" className="bouton bouton--secondaire">
                {estArabe ? 'اختر ملف PDF' : 'Parcourir un fichier PDF'}
              </label>
              <span className="texte-doux">
                {estArabe
                  ? 'أو اسحب وأفلت الملف هنا (عقد كراء، وعد بيع، مسح ضوئي...)'
                  : 'ou glissez-déposez votre contrat ici (PDF)'}
              </span>
            </div>
          )}
        </div>
      ) : (
        <div className="analyseur-document__zone-texte">
          <textarea
            className="champ-saisie champ-saisie--zone"
            rows={8}
            placeholder={
              estArabe
                ? 'الصق هنا نص العقد أو الوثيقة المراد فحصها...'
                : 'Collez ici le texte du contrat ou de la promesse de vente...'
            }
            value={texteSaisi}
            onChange={(e) => setTexteSaisi(e.target.value)}
          />
          <div className="analyseur-document__actions-texte">
            <button
              type="button"
              className="bouton bouton--neutre bouton--compact"
              onClick={() => {
                setTexteSaisi(exempleContratLocation)
                setTransaction('location')
              }}
            >
              {estArabe ? '📌 تجربة مثال توضيحي (عقد به نقص)' : '📌 Charger un exemple avec anomalies'}
            </button>
            {texteSaisi && (
              <button
                type="button"
                className="bouton bouton--neutre bouton--compact"
                onClick={() => setTexteSaisi('')}
              >
                {estArabe ? 'مسح' : 'Effacer'}
              </button>
            )}
          </div>
        </div>
      )}

      {erreur && <div className="alerte alerte--erreur">{erreur}</div>}

      {/* Bouton de lancement de l'analyse */}
      <div className="analyseur-document__action-principale">
        <button
          type="button"
          className="bouton bouton--principal"
          onClick={lancerAnalyse}
          disabled={chargement || (modeSaisie === 'fichier' && !fichier) || (modeSaisie === 'texte' && !texteSaisi.trim())}
        >
          {chargement
            ? estArabe
              ? '⏳ جاري الفحص واستخراج البيانات...'
              : '⏳ Analyse et extraction en cours...'
            : estArabe
              ? '🔍 فحص واكتشاف النواقص'
              : '🔍 Lancer l’audit documentaire'}
        </button>
      </div>

      {/* Affichage des Résultats de l'analyse */}
      {rapport && (
        <div className="analyseur-document__rapport" data-testid="rapport-analyse">
          <div className="analyseur-document__rapport-entete">
            <div>
              <span
                className={`badge ${
                  rapport.statut_document === 'valide' ? 'badge--succes' : 'badge--jaune'
                }`}
              >
                {rapport.statut_document === 'valide'
                  ? estArabe
                    ? '✅ مستند مكتمل ومطابق مبدئياً'
                    : '✅ Document complet et conforme'
                  : estArabe
                    ? '⚠️ مستند يتطلب استكمال بيانات أو صفحات'
                    : '⚠️ Document incomplet / À compléter'}
              </span>
              <h4 style={{ margin: '0.5rem 0 0.25rem 0' }}>
                {estArabe
                  ? `تقرير التدقيق — معاملة : ${rapport.transaction === 'location' ? 'كراء' : 'بيع'}`
                  : `Rapport d'audit — Dossier : ${rapport.transaction === 'location' ? 'Location' : 'Vente'}`}
              </h4>
            </div>

            <div className="analyseur-document__score-box">
              <span className="analyseur-document__score-chiffre">
                {rapport.audit_checklist?.pourcentage_completude || 0} %
              </span>
              <span className="texte-doux" style={{ fontSize: '0.75rem' }}>
                {estArabe ? 'نسبة اكتمال الوثائق' : 'Complétude checklist'}
              </span>
            </div>
          </div>

          {/* Alertes et anomalies détectées */}
          {rapport.alertes && rapport.alertes.length > 0 && (
            <div className="alerte alerte--jaune" style={{ marginTop: '1rem' }}>
              <strong>{estArabe ? '🚨 تنبيهات وملاحظات تم رصدها :' : '🚨 Points de vigilance détectés :'}</strong>
              <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: estArabe ? 0 : '1.25rem', paddingRight: estArabe ? '1.25rem' : 0 }}>
                {rapport.alertes.map((alerte, aIdx) => (
                  <li key={aIdx}>{alerte}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Grille des résultats : Pagination & Données extraites */}
          <div className="analyseur-document__grille-resultats">
            {/* Colonne 1 : Pagination et structure */}
            <div className="analyseur-document__bloc">
              <h5>📑 {estArabe ? 'هيكلة الصفحات والترقيم' : 'Pagination & Intégrité'}</h5>
              <ul className="analyseur-document__liste-faits">
                <li>
                  <strong>{estArabe ? 'عدد الصفحات الفعلي :' : 'Nombre de pages physiques :'}</strong>{' '}
                  {rapport.pagination?.total_physique || 1}
                </li>
                {rapport.pagination?.total_annonce && (
                  <li>
                    <strong>{estArabe ? 'العدد المذكور بالعقد :' : 'Nombre mentionné :'}</strong>{' '}
                    {rapport.pagination.total_annonce}
                  </li>
                )}
                <li>
                  <strong>{estArabe ? 'سلسلة الترقيم :' : 'Numéros imprimés repérés :'}</strong>{' '}
                  {rapport.pagination?.numeros_detectes?.length > 0
                    ? rapport.pagination.numeros_detectes.join(', ')
                    : estArabe
                      ? 'غير مرقم'
                      : 'Non détecté'}
                </li>
                <li>
                  <strong>{estArabe ? 'حالة الترقيم :' : 'Conformité de pagination :'}</strong>{' '}
                  {rapport.pagination?.pagination_conforme ? (
                    <span className="badge badge--succes">{estArabe ? 'سليم' : 'Conforme'}</span>
                  ) : (
                    <span className="badge badge--rouge">{estArabe ? 'انقطاع أو نقص' : 'Saut / anomalie'}</span>
                  )}
                </li>
              </ul>
            </div>

            {/* Colonne 2 : Données juridiques & contractuelles extraites */}
            <div className="analyseur-document__bloc">
              <h5>🔍 {estArabe ? 'البيانات المستخرجة' : 'Données et mentions extraites'}</h5>
              <ul className="analyseur-document__liste-faits">
                <li>
                  <strong>{estArabe ? 'بطاقات التعريف (CIN) :' : 'Cartes d’identité (CIN) :'}</strong>{' '}
                  {rapport.champs_extraits?.cins_trouvees?.length > 0
                    ? rapport.champs_extraits.cins_trouvees.join(', ')
                    : estArabe
                      ? 'لم يتم العثور على بطاقات تعريف'
                      : 'Aucune CIN à 8 chiffres détectée'}
                </li>
                <li>
                  <strong>{estArabe ? 'المبالغ المالية المرصودة :' : 'Montants identifiés :'}</strong>{' '}
                  {rapport.champs_extraits?.montants_trouves?.length > 0
                    ? rapport.champs_extraits.montants_trouves.join(', ') + ' DT'
                    : estArabe
                      ? 'لم يتم رصد مبلغ واضح'
                      : 'Aucun montant en DT identifié'}
                </li>
                <li>
                  <strong>{estArabe ? 'التواريخ المذكورة :' : 'Dates mentionnées :'}</strong>{' '}
                  {rapport.champs_extraits?.dates_trouvees?.length > 0
                    ? rapport.champs_extraits.dates_trouvees.slice(0, 3).join(', ')
                    : estArabe
                      ? 'لا يوجد'
                      : 'Aucune'}
                </li>
                <li>
                  <strong>{estArabe ? 'الإمضاء / البلدية :' : 'Signatures / Légalisation :'}</strong>{' '}
                  {rapport.champs_extraits?.signature_detectee ? (
                    <span className="badge badge--succes">{estArabe ? 'مذكورة' : 'Détectée(s)'}</span>
                  ) : (
                    <span className="badge badge--rouge">{estArabe ? 'غير مذكورة' : 'Absente(s)'}</span>
                  )}
                </li>
                <li>
                  <strong>{estArabe ? 'حقول فارغة بحاجة للملء :' : 'Champs vides restants :'}</strong>{' '}
                  {rapport.champs_extraits?.nb_champs_vides || 0}
                </li>
              </ul>
            </div>
          </div>

          {/* Synthèse Checklist : Pièces présentes et manquantes */}
          {rapport.audit_checklist && (
            <div className="analyseur-document__checklist-synthese">
              <h5>📋 {estArabe ? 'مطابقة قائمة الوثائق الرسمية' : 'Audit de complétude de la checklist'}</h5>
              <div className="analyseur-document__checklist-colonnes">
                <div className="analyseur-document__col-pieces">
                  <span className="badge badge--succes" style={{ marginBottom: '0.5rem', display: 'inline-block' }}>
                    {estArabe ? 'وثائق موجودة أو مشمولة' : 'Pièces fournies / identifiées'} (
                    {rapport.audit_checklist.elements_fournis?.length || 0})
                  </span>
                  <ul>
                    {rapport.audit_checklist.elements_fournis?.map((id) => (
                      <li key={id}>✓ {id}</li>
                    ))}
                  </ul>
                </div>

                <div className="analyseur-document__col-pieces">
                  <span className="badge badge--rouge" style={{ marginBottom: '0.5rem', display: 'inline-block' }}>
                    {estArabe ? 'وثائق لا تزال ناقصة' : 'Justificatifs encore manquants'} (
                    {rapport.audit_checklist.elements_manquants?.length || 0})
                  </span>
                  <ul>
                    {rapport.audit_checklist.elements_manquants?.map((item, idx) => (
                      <li key={idx}>✕ {estArabe ? item.nom_ar : item.nom_fr}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Recommandations Diwan */}
          {rapport.recommandations_diwan && (
            <div className="analyseur-document__recommandations">
              <strong>💡 {estArabe ? 'توصيات ديوان والإدارة التونسية :' : 'Conseils officiels (Diwan & Fiscalité) :'}</strong>
              <ul>
                {rapport.recommandations_diwan.map((rec, rIdx) => (
                  <li key={rIdx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
