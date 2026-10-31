import { Link } from 'react-router-dom'
import AnnonceCarte from '../components/AnnonceCarte'
import MessageErreur from '../components/MessageErreur'
import RechercheRapide from '../components/RechercheRapide'
import { useAnnonces } from '../hooks/useAnnonces'
import { LIBELLES_TYPE_BIEN } from '../utils/format'

export const NB_DERNIERES_ANNONCES = 6

/** Page d'accueil publique : bannière avec recherche rapide, dernières annonces publiées, types de bien. */
export default function AccueilPage() {
  const { etat, donnees, erreur, reessayer } = useAnnonces({
    statut: 'publiee',
    page: 1,
    per_page: NB_DERNIERES_ANNONCES,
  })

  return (
    <div className="accueil">
      <section className="hero" aria-labelledby="titre-accueil">
        <div className="hero__titre-ligne">
          <h1 id="titre-accueil">Trouvez le bien qui vous correspond</h1>
          <span className="hero__badge-pill">Onglets Vente / Location</span>
        </div>
        <p className="hero__texte">Appartements, maisons, villas et studios à louer ou à vendre.</p>
        <RechercheRapide />
      </section>

      <section className="section" aria-labelledby="titre-dernieres">
        <div className="section__entete">
          <h2 id="titre-dernieres">Dernières annonces</h2>
          <Link to="/annonces">Voir toutes les annonces →</Link>
        </div>
        {etat === 'chargement' && (
          <p className="etat" role="status">
            Chargement des annonces…
          </p>
        )}
        {etat === 'erreur' && <MessageErreur erreur={erreur} onReessayer={reessayer} />}
        {etat === 'succes' && donnees.items.length === 0 && (
          <p className="etat etat--vide">Aucune annonce publiée pour le moment.</p>
        )}
        {etat === 'succes' && donnees.items.length > 0 && (
          <>
            <ul className="grille grille--4-colonnes" aria-label="Dernières annonces publiées">
              {donnees.items.map((annonce) => (
                <li key={annonce.id}>
                  <AnnonceCarte annonce={annonce} niveauTitre={3} />
                </li>
              ))}
            </ul>
            <div className="accueil__charger-plus">
              <Link to="/annonces" className="bouton accueil__btn-charger-plus">
                Charger plus d’annonces
              </Link>
            </div>
          </>
        )}
      </section>

      <section className="section" aria-labelledby="titre-types">
        <h2 id="titre-types">Parcourir par type de bien</h2>
        <ul className="types">
          {Object.entries(LIBELLES_TYPE_BIEN).map(([valeur, libelle]) => (
            <li key={valeur}>
              <Link className="types__lien" to={`/annonces?type_bien=${valeur}`}>
                {libelle}
                <span aria-hidden="true">→</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
