import { useState } from 'react'
import { genererContrat } from '../api/rag'

/**
 * Générateur de projet de contrat immobilier conforme au droit tunisien.
 * Permet de générer un bail d'habitation ou une promesse de vente
 * en français ou en arabe avec clauses de légalisation et enregistrement.
 *
 * @param {object} props
 * @param {string} [props.typeInitial] 'location' ou 'vente'.
 * @param {string} [props.langueInitiale] 'fr' ou 'ar'.
 */
export default function GenerateurContrat({ typeInitial = 'location', langueInitiale = 'fr' }) {
  const [typeContrat, setTypeContrat] = useState(typeInitial)
  const [langue, setLangue] = useState(langueInitiale)
  const [chargement, setChargement] = useState(false)
  const [contratGenere, setContratGenere] = useState('')
  const [copieSucces, setCopieSucces] = useState(false)
  const [erreur, setErreur] = useState(null)

  // Formulaire avec valeurs réalistes par défaut
  const [form, setForm] = useState({
    bailleur_nom: 'Mohamed Ben Salem',
    bailleur_cin: '08765432',
    bailleur_adresse: '12 Avenue Habib Bourguiba',
    bailleur_ville: 'Tunis',

    locataire_nom: 'Nour Trabelsi',
    locataire_cin: '11223344',
    locataire_qualite: 'Étudiante',
    avec_garant: true,
    garant_nom: 'Salah Trabelsi',
    garant_cin: '05443322',

    bien_type: 'appartement',
    bien_adresse: 'Résidence Les Jasmins, Apt 4B, Ennasr 2',
    bien_ville: 'Ariana',
    bien_surface: 75,
    bien_pieces: 3,
    bien_meuble: true,

    prix_ou_loyer: 850,
    caution_ou_avance: 850,
    duree: 'une (1) année renouvelable par tacite reconduction',
  })

  const estArabe = langue === 'ar'

  function majChamp(nom, valeur) {
    setForm((prev) => ({ ...prev, [nom]: valeur }))
  }

  async function handleGenerer(e) {
    if (e) e.preventDefault()
    setChargement(true)
    setErreur(null)
    setCopieSucces(false)

    try {
      const payload = {
        type_contrat: typeContrat,
        langue,
        bailleur: {
          nom_complet: form.bailleur_nom,
          cin: form.bailleur_cin,
          adresse: form.bailleur_adresse,
          ville: form.bailleur_ville,
        },
        locataire: {
          nom_complet: form.locataire_nom,
          cin: form.locataire_cin,
          qualite: form.locataire_qualite,
          garant: form.avec_garant
            ? {
                nom: form.garant_nom,
                cin: form.garant_cin,
              }
            : null,
        },
        bien: {
          type_bien: form.bien_type,
          adresse: form.bien_adresse,
          ville: form.bien_ville,
          surface: form.bien_surface,
          nb_pieces: form.bien_pieces,
          meuble: form.bien_meuble,
        },
        conditions: {
          loyer: form.prix_ou_loyer,
          prix_total: form.prix_ou_loyer,
          caution: form.caution_ou_avance,
          avance_arrhes: form.caution_ou_avance,
          duree: form.duree,
        },
      }

      const rep = await genererContrat(payload)
      setContratGenere(rep.contrat_markdown || '')
    } catch {
      setErreur(
        estArabe
          ? 'حدث خطأ أثناء صياغة العقد. الرجاء المحاولة مجدداً.'
          : 'Une erreur est survenue lors de la génération du projet de contrat.',
      )
    } finally {
      setChargement(false)
    }
  }

  async function copierDansPressePapier() {
    if (!contratGenere) return
    try {
      await navigator.clipboard.writeText(contratGenere)
      setCopieSucces(true)
      setTimeout(() => setCopieSucces(false), 3000)
    } catch {
      // Échec presse-papier silencieux
    }
  }

  function telechargerContrat() {
    if (!contratGenere) return
    const blob = new Blob([contratGenere], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const lien = document.createElement('a')
    lien.href = url
    lien.download = `projet_contrat_${typeContrat}_${langue}.md`
    document.body.appendChild(lien)
    lien.click()
    document.body.removeChild(lien)
    URL.revokeObjectURL(url)
  }

  return (
    <div className={`generateur-contrat ${estArabe ? 'generateur-contrat--rtl' : ''}`} dir={estArabe ? 'rtl' : 'ltr'}>
      <div className="generateur-contrat__entete">
        <div className="generateur-contrat__titre-groupe">
          <span className="badge badge--principal">Assistant Juridique</span>
          <h3 className="generateur-contrat__titre">
            {estArabe ? 'توليد مشروع عقد قانوني تونسي' : 'Générateur de projet de contrat conforme'}
          </h3>
        </div>
        <p className="generateur-contrat__sous-titre">
          {estArabe
            ? 'صياغة مشروع عقد كراء أو وعد بيع يستجيب للتشريع التونسي (مجلة الالتزامات والعقود، والفصل 377 مكرر، وشروط البلدية والقباضة المالية).'
            : 'Créez un projet de bail ou de promesse de vente intégrant les clauses obligatoires (COC tunisien, légalisation Baladiya et enregistrement fiscal).'}
        </p>
      </div>

      {/* Options : Type et Langue */}
      <div className="generateur-contrat__barre-options">
        <div className="generateur-contrat__selecteurs">
          <button
            type="button"
            className={`generateur-contrat__btn-type ${typeContrat === 'location' ? 'actif' : ''}`}
            onClick={() => setTypeContrat('location')}
          >
            {estArabe ? '🔑 عقد كراء سكنى' : '🔑 Bail d’habitation (Location)'}
          </button>
          <button
            type="button"
            className={`generateur-contrat__btn-type ${typeContrat === 'vente' ? 'actif' : ''}`}
            onClick={() => setTypeContrat('vente')}
          >
            {estArabe ? '🏛️ وعد بيع عقاري' : '🏛️ Promesse de vente'}
          </button>
        </div>

        <div className="generateur-contrat__langues">
          <button
            type="button"
            className={`generateur-contrat__btn-langue ${langue === 'fr' ? 'actif' : ''}`}
            onClick={() => setLangue('fr')}
          >
            Français
          </button>
          <button
            type="button"
            className={`generateur-contrat__btn-langue ${langue === 'ar' ? 'actif' : ''}`}
            onClick={() => setLangue('ar')}
          >
            العربية
          </button>
        </div>
      </div>

      {/* Formulaire de personnalisation des clauses */}
      <form onSubmit={handleGenerer} className="generateur-contrat__formulaire">
        <div className="generateur-contrat__grille-champs">
          {/* Bloc 1 : Bailleur / Vendeur */}
          <div className="generateur-contrat__section-form">
            <h4>👤 {typeContrat === 'location' ? (estArabe ? 'المؤجر (المالك)' : 'Bailleur (Propriétaire)') : (estArabe ? 'البائع' : 'Vendeur')}</h4>
            <div className="champ">
              <label htmlFor="bailleur_nom">{estArabe ? 'الاسم واللقب' : 'Nom complet'}</label>
              <input
                id="bailleur_nom"
                type="text"
                className="champ-saisie"
                value={form.bailleur_nom}
                onChange={(e) => majChamp('bailleur_nom', e.target.value)}
                required
              />
            </div>
            <div className="champ">
              <label htmlFor="bailleur_cin">{estArabe ? 'رقم بطاقة التعريف (CIN)' : 'N° Carte d’identité (8 chiffres)'}</label>
              <input
                id="bailleur_cin"
                type="text"
                className="champ-saisie"
                value={form.bailleur_cin}
                onChange={(e) => majChamp('bailleur_cin', e.target.value)}
                maxLength={8}
                required
              />
            </div>
            <div className="champ">
              <label htmlFor="bailleur_ville">{estArabe ? 'المدينة' : 'Ville'}</label>
              <input
                id="bailleur_ville"
                type="text"
                className="champ-saisie"
                value={form.bailleur_ville}
                onChange={(e) => majChamp('bailleur_ville', e.target.value)}
              />
            </div>
          </div>

          {/* Bloc 2 : Locataire / Acheteur */}
          <div className="generateur-contrat__section-form">
            <h4>👥 {typeContrat === 'location' ? (estArabe ? 'المكتري (المستأجر)' : 'Locataire (Preneur)') : (estArabe ? 'المشتري' : 'Acquéreur')}</h4>
            <div className="champ">
              <label htmlFor="locataire_nom">{estArabe ? 'الاسم واللقب' : 'Nom complet'}</label>
              <input
                id="locataire_nom"
                type="text"
                className="champ-saisie"
                value={form.locataire_nom}
                onChange={(e) => majChamp('locataire_nom', e.target.value)}
                required
              />
            </div>
            <div className="champ">
              <label htmlFor="locataire_cin">{estArabe ? 'رقم بطاقة التعريف (CIN)' : 'N° Carte d’identité (8 chiffres)'}</label>
              <input
                id="locataire_cin"
                type="text"
                className="champ-saisie"
                value={form.locataire_cin}
                onChange={(e) => majChamp('locataire_cin', e.target.value)}
                maxLength={8}
                required
              />
            </div>
            {typeContrat === 'location' && (
              <div className="champ">
                <label className="checkbox-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.avec_garant}
                    onChange={(e) => majChamp('avec_garant', e.target.checked)}
                  />
                  <span>{estArabe ? 'طالب مع كفيل وضامن تضامني (الولي)' : 'Étudiant avec caution parentale (Garant)'}</span>
                </label>
              </div>
            )}
            {typeContrat === 'location' && form.avec_garant && (
              <div className="champ" style={{ marginTop: '0.25rem' }}>
                <input
                  type="text"
                  className="champ-saisie"
                  placeholder={estArabe ? 'اسم ولقب الضامن ورقم بطاقة تعريفه' : 'Nom et CIN du parent garant'}
                  value={form.garant_nom}
                  onChange={(e) => majChamp('garant_nom', e.target.value)}
                />
              </div>
            )}
          </div>

          {/* Bloc 3 : Le bien immobilier */}
          <div className="generateur-contrat__section-form">
            <h4>🏠 {estArabe ? 'العقار ومواصفاته' : 'Description du bien'}</h4>
            <div className="champ">
              <label htmlFor="bien_adresse">{estArabe ? 'العنوان التفصيلي' : 'Adresse complète'}</label>
              <input
                id="bien_adresse"
                type="text"
                className="champ-saisie"
                value={form.bien_adresse}
                onChange={(e) => majChamp('bien_adresse', e.target.value)}
                required
              />
            </div>
            <div className="champ-ligne-double" style={{ display: 'flex', gap: '0.5rem' }}>
              <div className="champ" style={{ flex: 1 }}>
                <label htmlFor="bien_ville">{estArabe ? 'المدينة' : 'Ville'}</label>
                <input
                  id="bien_ville"
                  type="text"
                  className="champ-saisie"
                  value={form.bien_ville}
                  onChange={(e) => majChamp('bien_ville', e.target.value)}
                />
              </div>
              <div className="champ" style={{ flex: 1 }}>
                <label htmlFor="bien_surface">{estArabe ? 'المساحة (م²)' : 'Surface (m²)'}</label>
                <input
                  id="bien_surface"
                  type="number"
                  className="champ-saisie"
                  value={form.bien_surface}
                  onChange={(e) => majChamp('bien_surface', e.target.value)}
                />
              </div>
            </div>
            {typeContrat === 'location' && (
              <div className="champ">
                <label className="checkbox-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.bien_meuble}
                    onChange={(e) => majChamp('bien_meuble', e.target.checked)}
                  />
                  <span>{estArabe ? 'شقة / محل مفروش ومجهز' : 'Logement meublé (avec inventaire)'}</span>
                </label>
              </div>
            )}
          </div>

          {/* Bloc 4 : Conditions financières & formalités */}
          <div className="generateur-contrat__section-form">
            <h4>💰 {estArabe ? 'الشروط المالية' : 'Conditions financières'}</h4>
            <div className="champ">
              <label htmlFor="prix_ou_loyer">
                {typeContrat === 'location'
                  ? (estArabe ? 'معين الكراء الشهري (DT)' : 'Loyer mensuel (en DT)')
                  : (estArabe ? 'ثمن البيع الإجمالي (DT)' : 'Prix de vente total (en DT)')}
              </label>
              <input
                id="prix_ou_loyer"
                type="number"
                className="champ-saisie"
                value={form.prix_ou_loyer}
                onChange={(e) => majChamp('prix_ou_loyer', e.target.value)}
                required
              />
            </div>
            <div className="champ">
              <label htmlFor="caution_ou_avance">
                {typeContrat === 'location'
                  ? (estArabe ? 'مبلغ الضمان المالي - Caution (DT)' : 'Dépôt de garantie / Caution (DT)')
                  : (estArabe ? 'العربون المسبق (DT)' : 'Avance / Arrhes (DT)')}
              </label>
              <input
                id="caution_ou_avance"
                type="number"
                className="champ-saisie"
                value={form.caution_ou_avance}
                onChange={(e) => majChamp('caution_ou_avance', e.target.value)}
                required
              />
            </div>
            {typeContrat === 'location' && (
              <div className="champ">
                <label htmlFor="duree">{estArabe ? 'مدة الكراء' : 'Durée du bail'}</label>
                <input
                  id="duree"
                  type="text"
                  className="champ-saisie"
                  value={form.duree}
                  onChange={(e) => majChamp('duree', e.target.value)}
                />
              </div>
            )}
          </div>
        </div>

        {erreur && <div className="alerte alerte--erreur">{erreur}</div>}

        <div className="generateur-contrat__actions-generer">
          <button type="submit" className="bouton bouton--principal" disabled={chargement}>
            {chargement
              ? estArabe
                ? '⏳ جاري تحرير العقد...'
                : '⏳ Rédaction du projet en cours...'
              : estArabe
                ? '📝 إنشاء مشروع العقد الرسمي'
                : '📝 Générer le projet de contrat'}
          </button>
        </div>
      </form>

      {/* Aperçu du contrat généré avec boutons d'action */}
      {contratGenere && (
        <div className="generateur-contrat__apercu" data-testid="apercu-contrat">
          <div className="generateur-contrat__apercu-barre">
            <span className="badge badge--succes">
              {estArabe ? '✨ مشروع العقد جاهز للطباعة والمراجعة' : '✨ Projet de contrat prêt'}
            </span>
            <div className="generateur-contrat__apercu-boutons">
              <button
                type="button"
                className="bouton bouton--secondaire bouton--compact"
                onClick={copierDansPressePapier}
              >
                {copieSucces
                  ? estArabe
                    ? '✅ تم النسخ !'
                    : '✅ Copié !'
                  : estArabe
                    ? '📋 نسخ النص'
                    : '📋 Copier'}
              </button>
              <button
                type="button"
                className="bouton bouton--principal bouton--compact"
                onClick={telechargerContrat}
              >
                {estArabe ? '💾 تحميل (.md)' : '💾 Télécharger'}
              </button>
            </div>
          </div>

          <pre className="generateur-contrat__contenu-texte" dir={estArabe ? 'rtl' : 'ltr'}>
            {contratGenere}
          </pre>

          <div className="alerte alerte--info" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            <strong>{estArabe ? 'تذكير قانوني هام :' : 'Rappel juridique important :'}</strong>{' '}
            {estArabe
              ? 'هذا النموذج استرشادي ويجب التعريف بإمضاء الطرفين بالبلدية (Baladiya) وتسجيله بالقباضة المالية خلال 60 يوماً. بالنسبة لعقود البيع، يستوجب الفصل 377 مكرر من مجلة الحقوق العينية تحريرها وجوباً بواسطة محام غير متمرن أو عدل إشهاد أو حافظ الملكية العقارية.'
              : "Ce modèle est fourni à titre indicatif. Il requiert la légalisation des signatures en mairie (Baladiya) et l'enregistrement à la Recette des Finances sous 60 jours. Pour les ventes, l'article 377 bis du CDR impose la rédaction de l'acte définitif par un notaire, un avocat habilité ou les rédacteurs de la CPF."}
          </div>
        </div>
      )}
    </div>
  )
}
