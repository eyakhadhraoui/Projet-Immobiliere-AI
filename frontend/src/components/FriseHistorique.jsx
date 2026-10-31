import { Link } from 'react-router-dom'
import { obtenirHistoriqueAnnonce } from '../api/historique'
import { useRequete } from '../hooks/useRequete'
import EntreeHistorique from './EntreeHistorique'
import MessageErreur from './MessageErreur'

/** Frise chronologique des actions sur une annonce (la plus récente en haut). */
export default function FriseHistorique({ annonceId }) {
  const { etat, donnees, erreur, reessayer } = useRequete(`historique-${annonceId}`, () =>
    obtenirHistoriqueAnnonce(annonceId),
  )

  return (
    <section className="fiche__section frise" aria-labelledby="titre-frise">
      <div className="section__entete">
        <h2 id="titre-frise">Historique</h2>
        <Link to={`/espace/historique?annonce_id=${annonceId}`}>Voir dans l'historique complet</Link>
      </div>
      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement de l'historique…
        </p>
      )}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}
      {etat === 'succes' && donnees.length === 0 && <p className="etat">Aucune action enregistrée pour cette annonce.</p>}
      {etat === 'succes' && donnees.length > 0 && (
        <ol className="frise__liste" aria-label="Actions sur l'annonce">
          {donnees.map((entree) => (
            <li key={entree.id}>
              <EntreeHistorique entree={entree} avecTitre={false} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
