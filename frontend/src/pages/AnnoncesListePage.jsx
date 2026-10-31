import { useSearchParams } from 'react-router-dom'
import FiltresAnnonces from '../components/FiltresAnnonces'
import ListeAnnonces from '../components/ListeAnnonces'
import MessageErreur from '../components/MessageErreur'
import { useAnnonces } from '../hooks/useAnnonces'
import {
  ANNONCES_PAR_PAGE,
  aDesFiltres,
  construireParams,
  FILTRES_VIDES,
  lireFiltres,
  lirePage,
} from '../utils/filtresUrl'

/**
 * Catalogue public : annonces publiées uniquement, paginées ; filtres et page sont lus depuis l'URL.
 * Le filtre de statut est imposé ici : il n'apparaît pas dans l'URL ni dans la barre de filtres.
 */
export default function AnnoncesListePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filtres = lireFiltres(searchParams)
  const page = lirePage(searchParams)
  const filtresApi = { ...filtres }
  if (filtresApi.tri === 'chronologique') delete filtresApi.tri
  const { etat, donnees, erreur, reessayer } = useAnnonces({
    ...filtresApi,
    statut: 'publiee',
    page,
    per_page: ANNONCES_PAR_PAGE,
  })

  function appliquerFiltres(nouveauxFiltres) {
    // Un nouveau filtre ramène toujours à la première page.
    setSearchParams(construireParams(nouveauxFiltres, 1))
  }

  function changerPage(nouvellePage) {
    setSearchParams(construireParams(filtres, nouvellePage))
  }

  return (
    <section className="page">
      <h1>Annonces</h1>
      <p className="page__intro">Toutes les annonces disponibles à la location et à la vente.</p>

      <FiltresAnnonces
        key={searchParams.toString()}
        valeurs={filtres}
        onAppliquer={appliquerFiltres}
        onReinitialiser={() => appliquerFiltres(FILTRES_VIDES)}
      />

      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement des annonces…
        </p>
      )}

      {etat === 'erreur' && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && (
        <ListeAnnonces
          donnees={donnees}
          filtresActifs={aDesFiltres(filtres)}
          onReinitialiser={() => appliquerFiltres(FILTRES_VIDES)}
          onChangerPage={changerPage}
        />
      )}
    </section>
  )
}
