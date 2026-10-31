/** Nombre d'annonces demandées par page (paramètre per_page de l'API). */
export const ANNONCES_PAR_PAGE = 12

/** Filtres de la barre de recherche, synchronisés avec l'URL (?ville=tunis&page=2). */
export const CLES_FILTRES = ['ville', 'type_bien', 'transaction', 'prix_min', 'prix_max', 'meuble', 'tri']

export const FILTRES_VIDES = { ...Object.fromEntries(CLES_FILTRES.map((cle) => [cle, ''])), tri: 'chronologique' }

/**
 * Lit les filtres présents dans l'URL.
 *
 * @param {URLSearchParams} searchParams Paramètres de l'URL courante.
 * @returns {Record<string, string>} Une entrée par filtre ('' si absent).
 */
export function lireFiltres(searchParams) {
  return Object.fromEntries(CLES_FILTRES.map((cle) => [
    cle,
    searchParams.get(cle) ?? (cle === 'tri' ? 'chronologique' : ''),
  ]))
}

/**
 * Lit le numéro de page dans l'URL (1 si absent ou invalide).
 *
 * @param {URLSearchParams} searchParams Paramètres de l'URL courante.
 * @returns {number} Numéro de page, supérieur ou égal à 1.
 */
export function lirePage(searchParams) {
  const page = Number.parseInt(searchParams.get('page') ?? '', 10)
  return Number.isInteger(page) && page >= 1 ? page : 1
}

/**
 * Construit les paramètres d'URL à partir des filtres et de la page.
 * Les filtres vides et la page 1 sont omis pour garder une URL courte.
 *
 * @param {Record<string, string>} filtres Valeurs des filtres.
 * @param {number} page Numéro de page.
 * @returns {Record<string, string>} Paramètres pour setSearchParams.
 */
export function construireParams(filtres, page = 1) {
  const params = {}
  for (const cle of CLES_FILTRES) {
    const valeur = (filtres[cle] ?? '').trim()
    if (valeur && !(cle === 'tri' && valeur === 'chronologique')) params[cle] = valeur
  }
  if (page > 1) params.page = String(page)
  return params
}

/** Indique si au moins un filtre est renseigné. */
export function aDesFiltres(filtres) {
  return CLES_FILTRES.some((cle) => cle !== 'tri' && (filtres[cle] ?? '').trim() !== '')
}
