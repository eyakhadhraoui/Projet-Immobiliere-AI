import { useEffect, useState } from 'react'
import { obtenirHistoriqueConnexions } from '../api/auth'

function dateLisible(date) {
  return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date))
}

/** Historique privé du compte : ne présente ni adresse IP ni empreinte technique. */
export default function HistoriqueConnexions() {
  const [items, setItems] = useState([])
  const [etat, setEtat] = useState('chargement')

  useEffect(() => {
    let actif = true
    obtenirHistoriqueConnexions()
      .then((resultat) => { if (actif) { setItems(resultat); setEtat('succes') } })
      .catch(() => { if (actif) setEtat('erreur') })
    return () => { actif = false }
  }, [])

  return (
    <section className="panneau profil__section" aria-labelledby="titre-historique-connexions">
      <h2 id="titre-historique-connexions">Historique des connexions</h2>
      {etat === 'chargement' && <p role="status">Chargement de l’historique…</p>}
      {etat === 'erreur' && <p role="alert">Impossible de charger l’historique des connexions.</p>}
      {etat === 'succes' && items.length === 0 && <p>Aucune connexion enregistrée.</p>}
      {etat === 'succes' && items.length > 0 && (
        <ol className="historique-connexions">
          {items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.reussie ? 'Connexion réussie' : 'Échec de connexion'}</strong>
                <span>{item.navigateur} · {item.appareil} · {item.lieu}</span>
              </div>
              <div className="historique-connexions__meta">
                <time dateTime={item.date}>{dateLisible(item.date)}</time>
                <span className={`historique-connexions__risque historique-connexions__risque--${item.risque}`}>
                  {item.risque === 'tres_eleve' ? 'Très élevé' : item.risque === 'suspect' ? 'À vérifier' : 'Faible'}
                </span>
                {item.retour && <small>{item.retour === 'confirmee' ? 'Confirmée par vous' : 'Signalée par vous'}</small>}
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="champ__aide">Les adresses IP et empreintes techniques ne sont pas affichées.</p>
    </section>
  )
}
