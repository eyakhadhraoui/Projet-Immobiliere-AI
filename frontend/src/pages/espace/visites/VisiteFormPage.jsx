import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { listerToutesLesAnnonces } from '../../../api/annonces'
import { creerVisite, modifierVisite, obtenirVisite } from '../../../api/visites'

export default function VisiteFormPage() {
  const { id } = useParams()
  const estModification = Boolean(id)
  const navigate = useNavigate()

  const [annonces, setAnnonces] = useState([])
  const [chargement, setChargement] = useState(true)
  const [soumission, setSoumission] = useState(false)
  const [erreur, setErreur] = useState(null)

  const [form, setForm] = useState({
    annonce_id: '',
    client_id: '',
    date_visite: '',
    heure_debut: '10:00',
    heure_fin: '11:00',
    statut: 'en_attente',
    type_visite: 'sur_place',
    nb_personnes: 1,
    telephone_contact: '98123456',
    message_client: '',
  })

  useEffect(() => {
    async function init() {
      try {
        const liste = await listerToutesLesAnnonces({ mes_annonces: true })
        setAnnonces(liste)

        if (estModification) {
          const vis = await obtenirVisite(id)
          setForm({
            annonce_id: vis.annonce_id || (liste[0]?.id ?? ''),
            client_id: vis.client_id || '',
            date_visite: vis.date_visite || '',
            heure_debut: vis.heure_debut || '10:00',
            heure_fin: vis.heure_fin || '11:00',
            statut: vis.statut || 'en_attente',
            type_visite: vis.type_visite || 'sur_place',
            nb_personnes: vis.nb_personnes || 1,
            telephone_contact: vis.telephone_contact || '',
            message_client: vis.message_client || '',
          })
        } else if (liste.length > 0) {
          const dateLocale = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().split('T')[0]
          setForm((prev) => ({ ...prev, annonce_id: liste[0].id, date_visite: dateLocale }))
        } else if (!estModification) {
          const dateLocale = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().split('T')[0]
          setForm((prev) => ({ ...prev, date_visite: dateLocale }))
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
        await modifierVisite(id, form)
        navigate(`/espace/visites/${id}`)
      } else {
        const nouv = await creerVisite(form)
        navigate(`/espace/visites/${nouv.id}`)
      }
    } catch (err) {
      setErreur(err.response?.data?.message || 'Erreur lors de la sauvegarde.')
    } finally {
      setSoumission(false)
    }
  }

  if (chargement) return <p className="etat">Chargement du formulaire…</p>

  return (
    <section className="page page--etroit">
      <div className="page__entete">
        <div>
          <h1>{estModification ? 'Modifier la visite' : 'Planifier une nouvelle visite'}</h1>
          <p className="texte-secondaire">Définissez la date, l'horaire et les coordonnées du visiteur.</p>
        </div>
        <Link to="/espace/visites" className="bouton bouton--secondaire">
          Retour à la liste
        </Link>
      </div>

      {erreur && <div className="panneau alerte--erreur">{erreur}</div>}

      <form onSubmit={handleSubmit} className="panneau formulaire-crud">
        <div className="form-groupe">
          <label htmlFor="annonce_id">Bien immobilier concerné *</label>
          <select
            id="annonce_id"
            name="annonce_id"
            value={form.annonce_id}
            onChange={handleChange}
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

        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="date_visite">Date de la visite *</label>
            <input
              type="date"
              id="date_visite"
              name="date_visite"
              value={form.date_visite}
              onChange={handleChange}
              required
              className="champ-saisie"
            />
          </div>

          <div className="form-groupe">
            <label htmlFor="type_visite">Format de visite *</label>
            <select
              id="type_visite"
              name="type_visite"
              value={form.type_visite}
              onChange={handleChange}
              className="champ-saisie"
            >
              <option value="sur_place">Sur place (en personne)</option>
              <option value="virtuelle">Virtuelle (visio / WhatsApp)</option>
            </select>
          </div>
        </div>

        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="heure_debut">Heure de début *</label>
            <input
              type="time"
              id="heure_debut"
              name="heure_debut"
              value={form.heure_debut}
              onChange={handleChange}
              required
              className="champ-saisie"
            />
          </div>

          <div className="form-groupe">
            <label htmlFor="heure_fin">Heure de fin *</label>
            <input
              type="time"
              id="heure_fin"
              name="heure_fin"
              value={form.heure_fin}
              onChange={handleChange}
              required
              className="champ-saisie"
            />
          </div>
        </div>

        <div className="form-grille-2">
          <div className="form-groupe">
            <label htmlFor="telephone_contact">Téléphone du contact *</label>
            <input
              type="tel"
              id="telephone_contact"
              name="telephone_contact"
              value={form.telephone_contact}
              onChange={handleChange}
              required
              placeholder="ex. 98123456"
              className="champ-saisie"
            />
          </div>

          <div className="form-groupe">
            <label htmlFor="nb_personnes">Nombre de personnes</label>
            <input
              type="number"
              id="nb_personnes"
              name="nb_personnes"
              min="1"
              max="10"
              value={form.nb_personnes}
              onChange={handleChange}
              className="champ-saisie"
            />
          </div>
        </div>

        {estModification && (
          <div className="form-groupe">
            <label htmlFor="statut">Statut de la visite</label>
            <select
              id="statut"
              name="statut"
              value={form.statut}
              onChange={handleChange}
              className="champ-saisie"
            >
              <option value="en_attente">En attente</option>
              <option value="confirmee">Confirmée</option>
              <option value="refusee">Refusée</option>
              <option value="annulee">Annulée</option>
              <option value="reportee">Reportée</option>
              <option value="effectuee">Effectuée</option>
              <option value="absent">Absent</option>
            </select>
          </div>
        )}

        <div className="form-groupe">
          <label htmlFor="message_client">Remarques ou instructions particulières</label>
          <textarea
            id="message_client"
            name="message_client"
            rows="3"
            value={form.message_client}
            onChange={handleChange}
            placeholder="Ex : Le client souhaite voir en priorité le balcon et le parking."
            className="champ-saisie"
          />
        </div>

        <div className="formulaire-actions">
          <Link to="/espace/visites" className="bouton bouton--secondaire">
            Annuler
          </Link>
          <button type="submit" disabled={soumission} className="bouton bouton--principal">
            {soumission ? 'Enregistrement…' : estModification ? 'Mettre à jour' : 'Créer la visite'}
          </button>
        </div>
      </form>
    </section>
  )
}
