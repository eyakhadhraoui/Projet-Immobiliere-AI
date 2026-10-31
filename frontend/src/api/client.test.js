import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, lireCookie, surFinDeSession } from './client'

/** Remplace le transport HTTP d'axios : chaque requête est enregistrée et reçoit la réponse choisie. */
function simulerServeur(repondre) {
  const requetes = []
  api.defaults.adapter = async (config) => {
    requetes.push({ url: config.url, methode: config.method, csrf: config.headers['X-CSRF-TOKEN'] })
    const { status, data = {} } = repondre(config, requetes.length)
    const reponse = { data, status, statusText: '', headers: {}, config }
    if (status >= 400) {
      const erreur = new Error(`HTTP ${status}`)
      Object.assign(erreur, { isAxiosError: true, config, response: reponse })
      throw erreur
    }
    return reponse
  }
  return requetes
}

function poserCookie(nom, valeur) {
  document.cookie = `${nom}=${encodeURIComponent(valeur)}; path=/`
}

function effacerCookies() {
  for (const nom of ['csrf_access_token', 'csrf_refresh_token']) {
    document.cookie = `${nom}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`
  }
}

const adapterOrigine = api.defaults.adapter

beforeEach(() => effacerCookies())
afterEach(() => {
  api.defaults.adapter = adapterOrigine
  effacerCookies()
})

describe('Client HTTP : jeton CSRF', () => {
  it('ajoute X-CSRF-TOKEN aux requêtes modifiantes, pas aux lectures', async () => {
    poserCookie('csrf_access_token', 'jeton-acces')
    const requetes = simulerServeur(() => ({ status: 200 }))

    await api.get('/annonces')
    await api.put('/auth/moi', { ville: 'Sousse' })
    await api.delete('/annonces/3')

    expect(requetes.map((r) => [r.methode, r.csrf])).toEqual([
      ['get', undefined],
      ['put', 'jeton-acces'],
      ['delete', 'jeton-acces'],
    ])
  })

  it('utilise le jeton CSRF de rafraîchissement pour /auth/rafraichir', async () => {
    poserCookie('csrf_access_token', 'jeton-acces')
    poserCookie('csrf_refresh_token', 'jeton-rafraichissement')
    const requetes = simulerServeur(() => ({ status: 200 }))

    await api.post('/auth/rafraichir')

    expect(requetes[0].csrf).toBe('jeton-rafraichissement')
  })

  it('ne lit que les cookies lisibles et ne stocke rien dans localStorage', async () => {
    poserCookie('csrf_access_token', 'jeton-acces')
    simulerServeur(() => ({ status: 200 }))
    await api.put('/auth/moi', {})

    expect(lireCookie('csrf_access_token')).toBe('jeton-acces')
    expect(lireCookie('access_token_cookie')).toBeNull() // httpOnly : invisible pour JavaScript
    expect(localStorage.length).toBe(0)
  })
})

describe('Client HTTP : rafraîchissement automatique de la session', () => {
  it('rafraîchit une seule fois puis rejoue les requêtes en 401', async () => {
    poserCookie('csrf_refresh_token', 'jeton-rafraichissement')
    let rafraichi = false
    const requetes = simulerServeur((config) => {
      if (config.url === '/auth/rafraichir') {
        rafraichi = true
        return { status: 200 }
      }
      return rafraichi ? { status: 200, data: { ok: config.url } } : { status: 401, data: { error: 'non_authentifie' } }
    })

    const [a, b] = await Promise.all([api.get('/statistiques'), api.get('/historique')])

    expect([a.data, b.data]).toEqual([{ ok: '/statistiques' }, { ok: '/historique' }])
    expect(requetes.filter((r) => r.url === '/auth/rafraichir')).toHaveLength(1)
  })

  it('signale la fin de session si le rafraîchissement échoue', async () => {
    poserCookie('csrf_refresh_token', 'jeton-rafraichissement')
    simulerServeur(() => ({ status: 401, data: { error: 'non_authentifie' } }))
    const ecouteur = vi.fn()
    const desabonner = surFinDeSession(ecouteur)

    await expect(api.get('/auth/moi')).rejects.toMatchObject({ response: { status: 401 } })

    expect(ecouteur).toHaveBeenCalledTimes(1)
    desabonner()
  })

  it("ne tente pas de rafraîchir sans session (visiteur) ni après un échec de connexion", async () => {
    const requetes = simulerServeur(() => ({ status: 401, data: { error: 'identifiants_invalides' } }))

    await expect(api.get('/auth/moi')).rejects.toBeTruthy()
    poserCookie('csrf_refresh_token', 'jeton-rafraichissement')
    await expect(api.post('/auth/connexion', {})).rejects.toBeTruthy()

    expect(requetes.map((r) => r.url)).toEqual(['/auth/moi', '/auth/connexion'])
  })
})
