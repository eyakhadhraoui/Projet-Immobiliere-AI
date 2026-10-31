import { useParams } from 'react-router-dom'
import FicheAnnonce from '../components/FicheAnnonce'
import MessageErreur from '../components/MessageErreur'
import { useAnnonce } from '../hooks/useAnnonce'
import PageIntrouvable from './PageIntrouvable'

/** Détail d'une annonce dans l'espace propriétaire : fiche complète, actions et frise d'historique. */
export default function DetailAnnoncePage() {
  const { id } = useParams()
  const { etat, annonce, erreur, reessayer, remplacerAnnonce } = useAnnonce(id, true)

  if (etat === 'introuvable') {
    return (
      <PageIntrouvable
        titre="Annonce introuvable"
        message={`L'annonce n° ${id} n'existe pas ou a été supprimée.`}
        lien={{ to: '/espace/annonces', libelle: '← Retour à mes annonces' }}
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
      {etat === 'succes' && <FicheAnnonce key={annonce.id} annonce={annonce} onAnnonceModifiee={remplacerAnnonce} espace />}
    </section>
  )
}
