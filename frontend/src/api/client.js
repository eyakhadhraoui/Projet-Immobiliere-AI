import axios from 'axios'

/**
 * Instance axios partagée par tous les modules d'API.
 * L'URL est relative : en développement, le proxy de Vite redirige "/api" vers Flask (même origine).
 *
 * Session (USER-002) : les jetons JWT sont dans des cookies httpOnly, illisibles par JavaScript et
 * envoyés automatiquement par le navigateur. Rien n'est stocké dans localStorage. Seul le jeton CSRF
 * (cookie lisible, par conception) est recopié dans l'en-tête X-CSRF-TOKEN des requêtes modifiantes.
 */
export const api = axios.create({
  baseURL: '/api',
  headers: { Accept: 'application/json' },
})

const METHODES_SURES = new Set(['get', 'head', 'options'])
const URL_RAFRAICHIR = '/auth/rafraichir'
// Un 401 sur ces routes est une réponse normale (identifiants faux, déjà déconnecté) : pas de rafraîchissement.
const URLS_SANS_RAFRAICHISSEMENT = new Set(['/auth/connexion', '/auth/inscription', URL_RAFRAICHIR, '/auth/deconnexion'])

/**
 * Lit un cookie lisible par JavaScript (les cookies httpOnly n'apparaissent jamais ici).
 *
 * @param {string} nom Nom du cookie.
 * @returns {string | null} Valeur décodée, ou null.
 */
export function lireCookie(nom) {
  const entree = document.cookie.split('; ').find((cookie) => cookie.startsWith(`${nom}=`))
  return entree ? decodeURIComponent(entree.slice(nom.length + 1)) : null
}

const ecouteursFinDeSession = new Set()

/**
 * Abonne une fonction à la fin de session (rafraîchissement impossible).
 *
 * @param {() => void} ecouteur Fonction appelée quand la session est perdue.
 * @returns {() => void} Fonction de désabonnement.
 */
export function surFinDeSession(ecouteur) {
  ecouteursFinDeSession.add(ecouteur)
  return () => ecouteursFinDeSession.delete(ecouteur)
}

function signalerFinDeSession() {
  ecouteursFinDeSession.forEach((ecouteur) => ecouteur())
}

api.interceptors.request.use((config) => {
  if (!METHODES_SURES.has((config.method ?? 'get').toLowerCase())) {
    const jeton = lireCookie(config.url === URL_RAFRAICHIR ? 'csrf_refresh_token' : 'csrf_access_token')
    if (jeton) config.headers['X-CSRF-TOKEN'] = jeton
  }
  return config
})

let rafraichissementEnCours = null

api.interceptors.response.use(
  (reponse) => reponse,
  async (error) => {
    const { config, response } = error
    const rejouable =
      response?.status === 401 && config && !config.dejaRejouee && !URLS_SANS_RAFRAICHISSEMENT.has(config.url)
    if (!rejouable) throw error

    // Pas de cookie de rafraîchissement : aucune session à prolonger (visiteur ou session fermée).
    if (!lireCookie('csrf_refresh_token')) {
      signalerFinDeSession()
      throw error
    }
    // Plusieurs requêtes en 401 en même temps : un seul rafraîchissement, partagé.
    rafraichissementEnCours ??= api.post(URL_RAFRAICHIR).finally(() => {
      rafraichissementEnCours = null
    })
    try {
      await rafraichissementEnCours
    } catch {
      signalerFinDeSession()
      throw error
    }
    return api({ ...config, dejaRejouee: true })
  },
)
