import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { listerToutesLesAnnonces } from '../../../api/annonces'
import { creerTransaction, modifierTransaction, obtenirTransaction } from '../../../api/transactions'

export default function TransactionFormPage() {
  const { id } = useParams()
  const estModification = Boolean(id)
  const navigate = useNavigate()

  const [annonces, setAnnonces] = useState([])
  const [chargement, setChargement] = useState(true)
  const [soumission, setSoumission] = useState(false)
  const [erreur, setErreur] = useState(null)

  const [form, setForm] = useState({
    annonce_id: '',
    type_transaction: 'vente',
    montant_total: '',
    acompte: 0,
    mode_paiement: 'virement',
    statut: 'en_cours',
    notaire: '',
    reference_acte: '',
    observations: '',
    date_signature: '',
  })

  useEffect(() => {
    async function init() {
      try {
        const liste = await listerToutesLesAnnonces({ mes_annonces: true })
        setAnnonces(liste)

        if (estModification) {
          const t = await obtenirTransaction(id)
          setForm({
            annonce_id: t.annonce_id || (liste[0]?.id ?? ''),
            type_transaction: t.type_transaction || 'vente',
            montant_total: t.montant_total || 0,
            acompte: t.acompte || 0,
            mode_paiement: t.mode_paiement || 'virement',
            statut: t.statut || 'en_cours',
            notaire: t.notaire || '',
            reference_acte: t.reference_acte || '',
            observations: t.observations || '',
            date_signature: t.date_signature || '',
          })
        } else if (liste.length > 0) {
          setForm((prev) => ({
            ...prev,
            annonce_id: liste[0].id,
            montant_total: liste[0].prix || '',
            acompte: 0,
          }))
        }
      } catch (e) {
        setErreur(e.message || 'Erreur de chargement')
      } finally {
        setChargement(false)
      }
    }
    init()
  }, [id, estModification])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSoumission(true)
    setErreur(null)

    try {
      if (estModification) {
        await modifierTransaction(id, form)
        navigate(`/espace/transactions/${id}`)
      } else {
        const nouv = await creerTransaction(form)
        navigate(`/espace/transactions/${nouv.id}`)
      }
    } catch (err) {
      setErreur(err.response?.data?.message || 'Erreur lors de la sauvegarde.')
    } finally {
      setSoumission(false)
    }
  }

  if (chargement) return <p className="etat">Chargement du formulaire…</p>

  return (
    <section className="page transaction-page">
      <div className="page__entete">
        <div>
          <h1>{estModification ? 'Modifier la transaction' : 'Nouvelle transaction'}</h1>
          <p className="texte-secondaire">Saisissez les montants en TND, l'acompte, le mode de paiement et l'acte notarié.</p>
        </div>
        <Link to="/espace/transactions" className="bouton bouton--secondaire">
          Retour à la liste
        </Link>
      </div>

      {erreur && <div className="panneau alerte--erreur">{erreur}</div>}

      <form onSubmit={handleSubmit} className="panneau formulaire-crud transaction-formulaire">
        <div className="form-groupe">
          <label htmlFor="annonce_id">Bien immobilier objet de la transaction *</label>
          <select
            id="annonce_id"
            name="annonce_id"
            value={form.annonce_id}
            onChange={(e) => {
              const selectedAnnonce = annonces.find((a) => String(a.id) === e.target.value)
              setForm((prev) => ({
                ...prev,
                annonce_id: e.target.value,
                montant_total: selectedAnnonce ? selectedAnnonce.prix : prev.montant_total,
              }))
            }}
            required
            className="champ-saisie"
          >
            {annonces.map((a) => (
              <option key={a.id} value={a.id}>
                {a.titre} — {a.ville} ({a.prix} TND)
              </option>
            ))}
          </select>
        </div>

        <h2 className="transaction-formulaire__titre"><span>1</span> Type et statut</h2>
        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="type_transaction">Type de transaction *</label>
            <select
              id="type_transaction"
              name="type_transaction"
              value={form.type_transaction}
              onChange={handleChange}
              className="champ-saisie"
            >
              <option value="vente">Vente définitive</option>
              <option value="location">Bail / Location</option>
              <option value="reservation">Promesse / Réservation</option>
            </select>
          </div>

          <div className="form-groupe">
            <label htmlFor="statut">Statut de la transaction *</label>
            <select
              id="statut"
              name="statut"
              value={form.statut}
              onChange={handleChange}
              className="champ-saisie"
            >
              <option value="en_negociation">En négociation</option>
              <option value="reservee">Réservée</option>
              <option value="en_cours">En cours</option>
              <option value="payee_partiellement">Payée partiellement</option>
              <option value="finalisee">Finalisée (Payée)</option>
              <option value="annulee">Annulée</option>
            </select>
          </div>
        </div>

        <h2 className="transaction-formulaire__titre"><span>2</span> Montants et paiement</h2>
        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="montant_total">Montant total (TND) *</label>
            <input
              type="number"
              id="montant_total"
              name="montant_total"
              step="0.001"
              min="0"
              value={form.montant_total}
              onChange={handleChange}
              required
              className="champ-saisie"
            />
          </div>

          <div className="form-groupe">
            <label htmlFor="acompte">Acompte / Avance versée (TND)</label>
            <input
              type="number"
              id="acompte"
              name="acompte"
              step="0.001"
              min="0"
              max={form.montant_total || undefined}
              value={form.acompte}
              onChange={handleChange}
              className="champ-saisie"
            />
          </div>
          <div className="form-groupe">
            <label htmlFor="reste-a-payer">Reste à payer (calculé)</label>
            <input
              id="reste-a-payer"
              value={Math.max(0, Number(form.montant_total || 0) - Number(form.acompte || 0)).toLocaleString('fr-TN')}
              readOnly
              className="champ-saisie champ-saisie--lecture-seule"
            />
          </div>
        </div>

        <h2 className="transaction-formulaire__titre"><span>3</span> Acte notarié</h2>
        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="mode_paiement">Mode de paiement *</label>
            <select
              id="mode_paiement"
              name="mode_paiement"
              value={form.mode_paiement}
              onChange={handleChange}
              className="champ-saisie"
            >
              <option value="virement">Virement bancaire</option>
              <option value="cheque">Chèque certifié</option>
              <option value="especes">Espèces</option>
              <option value="carte">Carte bancaire</option>
              <option value="flouci">Flouci</option>
              <option value="paymee">Paymee</option>
            </select>
          </div>

          <div className="form-groupe">
            <label htmlFor="date_signature">Date de signature prévue / effectuée</label>
            <input
              type="date"
              id="date_signature"
              name="date_signature"
              value={form.date_signature}
              onChange={handleChange}
              className="champ-saisie"
            />
          </div>
        </div>

        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="notaire">Notaire ou avocat rédacteur</label>
            <input
              type="text"
              id="notaire"
              name="notaire"
              value={form.notaire}
              onChange={handleChange}
              placeholder="Ex : Maître F. Ben Amor"
              className="champ-saisie"
            />
          </div>

          <div className="form-groupe">
            <label htmlFor="reference_acte">N° d'enregistrement / Référence acte</label>
            <input
              type="text"
              id="reference_acte"
              name="reference_acte"
              value={form.reference_acte}
              onChange={handleChange}
              placeholder="Ex : REC-FIN-2026/044"
              className="champ-saisie"
            />
          </div>
        </div>

        <div className="form-groupe">
          <label htmlFor="observations">Remarques et clauses particulières</label>
          <textarea
            id="observations"
            name="observations"
            rows="3"
            value={form.observations}
            onChange={handleChange}
            placeholder="Ex : Solde payable par chèque certifié le jour de la remise des clés."
            className="champ-saisie"
          />
        </div>

        <div className="formulaire-actions">
          <Link to="/espace/transactions" className="bouton bouton--secondaire">
            Annuler
          </Link>
          <button type="submit" disabled={soumission} className="bouton bouton--principal">
            {soumission ? 'Enregistrement…' : estModification ? 'Mettre à jour' : 'Créer la transaction'}
          </button>
        </div>
      </form>
    </section>
  )
}
