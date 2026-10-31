import { Link } from 'react-router-dom'
import photoIndisponible from '../assets/photo-indisponible.svg'
import { formaterDate, formaterPrix } from '../utils/format'
import { COLONNES_TRI } from '../utils/tableAnnonces'
import BadgeStatut from './BadgeStatut'
import EnteteTri from './EnteteTri'

/**
 * Tableau des annonces de l'espace propriétaire.
 * Sur petit écran, chaque ligne s'affiche comme une carte (libellés via data-label).
 */
export default function TableauAnnonces({ annonces, tri, onTrier, idEnCours, onBasculerPublication, onDemanderRevue, onSupprimer, analyses = {}, analyseEnCours, onAnalyser }) {
  return (
    <div className="tableau-conteneur">
      <table className="tableau">
        <caption className="visuellement-cache">Mes annonces (cliquez sur un en-tête de colonne pour trier)</caption>
        <thead>
          <tr>
            <th scope="col">
              <span className="visuellement-cache">Photo</span>
            </th>
            {Object.entries(COLONNES_TRI).map(([colonne, libelle]) => (
              <EnteteTri key={colonne} colonne={colonne} libelle={libelle} tri={tri} onTrier={onTrier} />
            ))}
            <th scope="col">Fiabilité</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {annonces.map((annonce) => {
            const photo = annonce.photos?.[0]
            const publiee = annonce.statut === 'publiee'
            const enAttenteFiabilite = annonce.statut === 'en_attente' && annonce.motif_attente === 'fiabilite'
            const occupe = idEnCours === annonce.id
            const libelleFiabilite = {
              aucun_signal: 'Aucun signal',
              a_surveiller: 'À surveiller',
              a_verifier: 'À vérifier',
            }[annonce.fiabilite?.niveau] || (enAttenteFiabilite ? 'En attente de vérification' : 'Non contrôlée')
            return (
              <tr key={annonce.id}>
                <td className="tableau__miniature">
                  <img src={photo ? photo.url : photoIndisponible} alt="" loading="lazy" />
                </td>
                <th scope="row" data-label="Titre" className="tableau__titre">
                  <Link to={`/espace/annonces/${annonce.id}`}>{annonce.titre}</Link>
                </th>
                <td data-label="Ville">{annonce.ville}</td>
                <td data-label="Prix" className="tableau__nombre">
                  {formaterPrix(annonce.prix, annonce.transaction)}
                </td>
                <td data-label="Statut">
                  <BadgeStatut statut={annonce.statut} />
                </td>
                <td data-label="Mise à jour">{formaterDate(annonce.updated_at)}</td>
                <td data-label="Fiabilité">
                  <span className={`fiabilite-badge fiabilite-badge--${annonce.fiabilite?.niveau || (enAttenteFiabilite ? 'attente' : 'inconnue')}`}>
                    {annonce.revue_demandee_le ? 'Réclamation envoyée' : libelleFiabilite}
                  </span>
                  {enAttenteFiabilite && !annonce.revue_demandee_le && (
                    <button type="button" className="bouton bouton--petit" onClick={() => onDemanderRevue(annonce)} disabled={occupe}>
                      Faire une réclamation
                    </button>
                  )}
                </td>
                <td data-label="Actions">
                  <div className="tableau__actions">
                    <Link
                      to={`/espace/annonces/${annonce.id}`}
                      className="bouton bouton--petit"
                      aria-label={`Voir « ${annonce.titre} »`}
                    >
                      Voir
                    </Link>
                    <Link
                      to={`/espace/annonces/${annonce.id}/modifier`}
                      className="bouton bouton--petit"
                      aria-label={`Modifier « ${annonce.titre} »`}
                    >
                      Modifier
                    </Link>
                    {!enAttenteFiabilite && <button
                      type="button"
                      className="bouton bouton--petit"
                      onClick={() => onBasculerPublication(annonce)}
                      disabled={occupe}
                      aria-label={`${publiee ? 'Dépublier' : 'Publier'} « ${annonce.titre} »`}
                    >
                      {publiee ? 'Dépublier' : 'Publier'}
                    </button>}
                    <button
                      type="button"
                      className="bouton bouton--petit bouton--danger"
                      onClick={() => onSupprimer(annonce)}
                      disabled={occupe}
                      aria-label={`Supprimer « ${annonce.titre} »`}
                    >
                      Supprimer
                    </button>
                    <button type="button" className="bouton bouton--petit" onClick={() => onAnalyser(annonce)}
                      disabled={analyseEnCours === annonce.id} aria-label={`Analyser l'atypicité de « ${annonce.titre} »`}>
                      {analyseEnCours === annonce.id ? 'Analyse…' : 'Vérifier atypicité'}
                    </button>
                  </div>
                  {analyses[annonce.id] && (
                    <p className="texte-secondaire" role="status">
                      {analyses[annonce.id].disponible
                        ? `Résultat exploratoire : ${analyses[annonce.id].niveau} · score relatif ${analyses[annonce.id].score_anomalie}`
                        : `Analyse indisponible : ${analyses[annonce.id].repli || 'données invalides'}`}
                      {analyses[annonce.id].facteurs?.length > 0 && ` · ${analyses[annonce.id].facteurs.join(' ; ')}`}
                    </p>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
