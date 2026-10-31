import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { agirMaintenance, obtenirMaintenance } from '../api/maintenance'
import { useAuth } from '../hooks/useAuth'
import { useRequete } from '../hooks/useRequete'

const ETAPES = ['signalee', 'acceptee', 'assignee', 'planifiee', 'cloturee']
const LABELS = { signalee: 'Signalée', acceptee: 'Acceptée', assignee: 'Assignée', planifiee: 'Planifiée', cloturee: 'Clôturée', refusee: 'Refusée' }
const CATEGORIES = { plomberie: '🔧 Plomberie', electricite: '⚡ Électricité', climatisation: '❄ Climatisation', serrurerie: '🔐 Serrurerie', electromenager: '🔌 Électroménager', autre: 'Autre' }

export default function MaintenanceDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { utilisateur } = useAuth()
  const proprio = utilisateur?.role === 'proprietaire'
  const retour = proprio ? '/espace/maintenance' : '/maintenance'
  const { donnees: item, etat, erreur, reessayer } = useRequete(['maintenance-detail', id], () => obtenirMaintenance(id))
  const [action, setAction] = useState('')
  const [erreurAction, setErreurAction] = useState('')
  const [technicien, setTechnicien] = useState({ technicien_nom: '', technicien_telephone: '' })
  const [planning, setPlanning] = useState({ date_intervention: '', cout_estime: '' })
  const [cloture, setCloture] = useState({ cout_reel: '', note_cloture: '' })
  async function appliquer(commande) {
    setAction(commande.action); setErreurAction('')
    try { await agirMaintenance(id, commande); reessayer() }
    catch (e) { setErreurAction(e.response?.data?.message || 'Impossible de mettre à jour cette demande.') }
    finally { setAction('') }
  }
  if (etat === 'chargement') return <p className="etat" role="status">Chargement du signalement…</p>
  if (etat !== 'succes' || !item) return <section className="page"><p className="etat etat--erreur">{erreur?.message || 'Signalement introuvable.'}</p><Link to={retour}>Retour à la liste</Link></section>
  const position = ETAPES.indexOf(item.statut)
  return <section className="page espace-page maintenance-detail">
    <div className="page__entete espace-page__entete"><div><h1>Demande de maintenance</h1><Link to={retour}>← Retour à la liste</Link></div>{proprio && item.statut === 'signalee' && <button className="bouton bouton--danger" disabled={!!action} onClick={() => appliquer({ action: 'refuser' })}>Refuser</button>}</div>
    {erreurAction && <p className="etat etat--erreur" role="alert">{erreurAction}</p>}
    <div className="maintenance-detail__grille">
      <div className="maintenance-detail__principal">
        <article className="panneau maintenance-detail__resume"><div className="maintenance-detail__ref"><span>{item.reference} · {CATEGORIES[item.categorie]}</span><span className={`maintenance-badge maintenance-badge--${item.priorite}`}>{item.priorite === 'urgente' ? 'Urgente' : item.priorite}</span><span className="maintenance-badge maintenance-badge--bleu">{LABELS[item.statut]}</span></div><h2>{item.titre}</h2><p>{item.description}</p>{item.photos?.length > 0 && <div className="maintenance-detail__photos">{item.photos.map((photo) => <a href={photo} target="_blank" rel="noreferrer" key={photo}><img src={photo} alt={`Photo jointe au signalement ${item.reference}`} /></a>)}</div>}</article>
        <article className="panneau maintenance-detail__suivi"><h2>Suivi de l’intervention</h2>{item.statut === 'refusee' ? <p className="maintenance-badge maintenance-badge--rouge">Demande refusée</p> : <ol className="maintenance__etapes">{ETAPES.map((step, index) => <li key={step} className={index < position ? 'terminee' : index === position ? 'active' : ''}><span>{index < position ? '✓' : index + 1}</span><small>{LABELS[step]}</small></li>)}</ol>}
          {item.technicien_nom && <p><strong>Technicien :</strong> {item.technicien_nom}{item.technicien_telephone ? ` · ${item.technicien_telephone}` : ''}</p>}
          {item.date_intervention && <p><strong>Intervention prévue :</strong> {new Date(item.date_intervention).toLocaleString('fr-FR')}</p>}
          {item.cout_estime != null && <p><strong>Coût estimé :</strong> {item.cout_estime} TND</p>}
          {item.statut === 'cloturee' && <p><strong>Coût réel :</strong> {item.cout_reel} TND {item.note_cloture && `· ${item.note_cloture}`}</p>}
          {proprio && item.statut === 'signalee' && <div className="maintenance-action"><p>Confirmez la prise en charge de cette demande.</p><button className="bouton bouton--principal" disabled={!!action} onClick={() => appliquer({ action: 'accepter' })}>{action === 'accepter' ? 'Acceptation…' : 'Accepter la demande'}</button></div>}
          {proprio && item.statut === 'acceptee' && <form className="maintenance-action" onSubmit={(e) => { e.preventDefault(); appliquer({ action: 'assigner', ...technicien }) }}><h3>Assigner un technicien</h3><label>Nom du technicien<input required value={technicien.technicien_nom} onChange={(e) => setTechnicien({ ...technicien, technicien_nom: e.target.value })} /></label><label>Téléphone<input value={technicien.technicien_telephone} onChange={(e) => setTechnicien({ ...technicien, technicien_telephone: e.target.value })} /></label><button className="bouton bouton--principal" disabled={!!action}>Assigner le technicien</button></form>}
          {proprio && item.statut === 'assignee' && <form className="maintenance-action" onSubmit={(e) => { e.preventDefault(); appliquer({ action: 'planifier', ...planning }) }}><h3>Planifier l’intervention</h3><label>Date et heure<input type="datetime-local" required value={planning.date_intervention} onChange={(e) => setPlanning({ ...planning, date_intervention: e.target.value })} /></label><label>Coût estimé (TND)<input type="number" min="0" step="0.001" value={planning.cout_estime} onChange={(e) => setPlanning({ ...planning, cout_estime: e.target.value })} /></label><button className="bouton bouton--principal" disabled={!!action}>Planifier</button></form>}
          {proprio && item.statut === 'planifiee' && <form className="maintenance-action" onSubmit={(e) => { e.preventDefault(); appliquer({ action: 'cloturer', ...cloture }) }}><h3>Clôturer l’intervention</h3><label>Coût réel (TND)<input type="number" required min="0" step="0.001" value={cloture.cout_reel} onChange={(e) => setCloture({ ...cloture, cout_reel: e.target.value })} /></label><label>Note de clôture<input value={cloture.note_cloture} onChange={(e) => setCloture({ ...cloture, note_cloture: e.target.value })} /></label><button className="bouton bouton--principal maintenance__cloturer" disabled={!!action}>Clôturer avec le coût réel</button></form>}
        </article>
      </div>
      <aside className="maintenance-detail__aside"><article className="panneau"><h2>Bien et locataire</h2><p>{item.annonce_titre}</p><p>Contrat actif · loyer {item.loyer_mensuel.toLocaleString('fr-FR')} TND/mois</p><p>Locataire : {item.locataire_nom} · {item.locataire_telephone || 'Téléphone non renseigné'}</p></article><article className="panneau"><div className="maintenance-detail__aside-titre"><h2>Historique</h2><span className="maintenance-badge maintenance-badge--vert">Enregistré</span></div><ol className="maintenance__timeline">{item.evenements.map((event) => <li key={event.id}><strong>{event.detail}</strong><time>{new Date(event.date_creation).toLocaleString('fr-FR')}</time></li>)}</ol></article></aside>
    </div>
  </section>
}
