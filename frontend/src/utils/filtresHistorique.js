/** Filtres de la page historique, synchronisés avec l'URL (?action=modification&page=2). */
export const CLES_FILTRES_HISTORIQUE = ['annonce_id', 'action', 'date_debut', 'date_fin']

export const FILTRES_HISTORIQUE_VIDES = Object.fromEntries(CLES_FILTRES_HISTORIQUE.map((cle) => [cle, '']))

export const ACTIONS_PAR_PAGE = 20

/** Lit les filtres de l'historique dans l'URL ('' si absent). */
export function lireFiltresHistorique(searchParams) {
  return Object.fromEntries(CLES_FILTRES_HISTORIQUE.map((cle) => [cle, searchParams.get(cle) ?? '']))
}

/** Paramètres d'URL de l'historique (filtres vides et page 1 omis). */
export function construireParamsHistorique(filtres, page = 1) {
  const params = {}
  for (const cle of CLES_FILTRES_HISTORIQUE) {
    const valeur = (filtres[cle] ?? '').trim()
    if (valeur) params[cle] = valeur
  }
  if (page > 1) params.page = String(page)
  return params
}

/**
 * Regroupe des entrées (déjà triées de la plus récente à la plus ancienne) par jour local.
 *
 * @param {object[]} entrees Entrées de l'historique.
 * @returns {{ jour: string, entrees: object[] }[]} Groupes dans le même ordre ; jour au format AAAA-MM-JJ.
 */
export function grouperParJour(entrees) {
  const groupes = []
  for (const entree of entrees) {
    const date = new Date(entree.created_at)
    const jour = [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
    const dernier = groupes.at(-1)
    if (dernier?.jour === jour) dernier.entrees.push(entree)
    else groupes.push({ jour, entrees: [entree] })
  }
  return groupes
}
