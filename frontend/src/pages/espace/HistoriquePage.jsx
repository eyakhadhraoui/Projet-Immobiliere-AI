import { useSearchParams } from 'react-router-dom'
import { listerToutesLesAnnonces } from '../../api/annonces'
import { listerHistorique } from '../../api/historique'
import EntreeHistorique from '../../components/EntreeHistorique'
import FiltresHistorique from '../../components/FiltresHistorique'
import MessageErreur from '../../components/MessageErreur'
import Pagination from '../../components/Pagination'
import { useRequete } from '../../hooks/useRequete'
import { lirePage } from '../../utils/filtresUrl'
import {
  ACTIONS_PAR_PAGE,
  FILTRES_HISTORIQUE_VIDES,
  construireParamsHistorique,
  grouperParJour,
  lireFiltresHistorique,
} from '../../utils/filtresHistorique'
import { formaterDate } from '../../utils/format'

/** Historique de toutes les actions, du plus récent au plus ancien, regroupé par jour ; filtres dans l'URL. */
export default function HistoriquePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filtres = lireFiltresHistorique(searchParams)
  const page = lirePage(searchParams)
  const cle = JSON.stringify({ ...filtres, page })
  const { etat, donnees, erreur, reessayer } = useRequete(cle, () =>
    listerHistorique({ ...JSON.parse(cle), per_page: ACTIONS_PAR_PAGE }),
  )
  // Liste des annonces pour le filtre (facultative : en cas d'échec, le filtre garde « Toutes »).
  const { donnees: annonces } = useRequete('annonces-du-filtre', () => listerToutesLesAnnonces({ mes_annonces: true }))

  function appliquer(nouveauxFiltres) {
    setSearchParams(construireParamsHistorique(nouveauxFiltres, 1))
  }

  return (
    <section className="page">
      <h1>Historique</h1>
      <p className="page__intro">Toutes les actions effectuées sur vos annonces, y compris les annonces supprimées.</p>

      <FiltresHistorique
        key={searchParams.toString()}
        valeurs={filtres}
        annonces={annonces ?? []}
        onAppliquer={appliquer}
        onReinitialiser={() => appliquer(FILTRES_HISTORIQUE_VIDES)}
      />

      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement de l'historique…
        </p>
      )}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && donnees.total === 0 && (
        <p className="etat etat--vide" role="status">
          Aucune action ne correspond à ces critères.
        </p>
      )}

      {etat === 'succes' && donnees.total > 0 && (
        <>
          {grouperParJour(donnees.items).map(({ jour, entrees }) => (
            <section key={jour} className="historique__jour">
              <h2 className="historique__date">{formaterDate(`${jour}T12:00:00`)}</h2>
              <ol className="historique__liste">
                {entrees.map((entree) => (
                  <li key={entree.id}>
                    <EntreeHistorique entree={entree} />
                  </li>
                ))}
              </ol>
            </section>
          ))}
          <Pagination
            page={donnees.page}
            totalPages={Math.ceil(donnees.total / donnees.per_page)}
            total={donnees.total}
            unite={['action', 'actions']}
            onChangerPage={(nouvelle) => setSearchParams(construireParamsHistorique(filtres, nouvelle))}
          />
        </>
      )}
    </section>
  )
}
