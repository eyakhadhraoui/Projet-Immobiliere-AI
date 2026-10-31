import { Link } from 'react-router-dom'
import { LIBELLES_ACTIONS, decrireDetails } from '../utils/historique'
import { formaterDateHeure } from '../utils/format'
import IconeAction from './IconeAction'

/**
 * Une action de l'historique : icône et couleur selon le type, titre de l'annonce,
 * action, détail des modifications et date.
 * avecTitre=false pour la frise d'une annonce (le titre est déjà celui de la page).
 */
export default function EntreeHistorique({ entree, avecTitre = true }) {
  const details = decrireDetails(entree)
  const action = LIBELLES_ACTIONS[entree.action] ?? entree.action

  return (
    <article className={`entree entree--${entree.action}`}>
      <span className="entree__icone">
        <IconeAction action={entree.action} />
      </span>
      <div className="entree__corps">
        <p className="entree__titre">
          {avecTitre && (
            <>
              {entree.action === 'suppression' ? (
                <span className="entree__annonce">{entree.titre_annonce}</span>
              ) : (
                <Link className="entree__annonce" to={`/espace/annonces/${entree.annonce_id}`}>
                  {entree.titre_annonce}
                </Link>
              )}
              {' — '}
            </>
          )}
          <span className="entree__action">{action}</span>
        </p>
        {details && <p className="entree__details">{details}</p>}
      </div>
      <time className="entree__date" dateTime={entree.created_at}>
        {formaterDateHeure(entree.created_at)}
      </time>
    </article>
  )
}
