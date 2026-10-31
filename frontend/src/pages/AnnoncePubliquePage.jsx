import { useParams } from 'react-router-dom'
import FicheAnnonce from '../components/FicheAnnonce'
import MessageErreur from '../components/MessageErreur'
import { useAnnonce } from '../hooks/useAnnonce'
import PageIntrouvable from './PageIntrouvable'

/** Fiche publique d'une annonce : seules les annonces publiées sont visibles des clients. */
export default function AnnoncePubliquePage() {
  const { id } = useParams()
  const { etat, annonce, erreur, reessayer } = useAnnonce(id)

  if (etat === 'introuvable' || (etat === 'succes' && annonce.statut !== 'publiee')) {
    return (
      <PageIntrouvable
        titre="Annonce indisponible"
        message="Cette annonce n'existe pas ou n'est plus en ligne."
        lien={{ to: '/annonces', libelle: '← Voir les annonces disponibles' }}
      />
    )
  }

  return (
    <section className="page">
      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement de l'annonce…
        </p>
      )}
      {etat === 'erreur' && (
        <>
          <h1>Annonce</h1>
          <MessageErreur erreur={erreur} onReessayer={reessayer} />
        </>
      )}
      {etat === 'succes' && <FicheAnnonce key={annonce.id} annonce={annonce} />}
    </section>
  )
}
