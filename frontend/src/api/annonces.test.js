import { AxiosError, CanceledError } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ajouterPhotos, api, changerStatut, lireErreur, listerAnnonces, listerToutesLesAnnonces, nettoyerFiltres } from './annonces'
import { listerHistorique, obtenirHistoriqueAnnonce, obtenirStatistiques } from './historique'

function erreurHttp(status, data) {
  return new AxiosError('Request failed', 'ERR_BAD_RESPONSE', {}, {}, { status, data, headers: {}, config: {}, statusText: '' })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('nettoyerFiltres', () => {
  it('retire les valeurs vides et les espaces', () => {
    expect(nettoyerFiltres({ ville: '  tunis ', type_bien: '', prix_min: undefined, meuble: null, page: 2 })).toEqual({
      ville: 'tunis',
      page: 2,
    })
  })
})

describe('fonctions de route', () => {
  it('listerAnnonces appelle GET /annonces avec les filtres nettoyés', async () => {
    const reponse = { items: [], page: 1, per_page: 12, total: 0 }
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: reponse })

    await expect(listerAnnonces({ ville: 'tunis', transaction: '' })).resolves.toEqual(reponse)
    expect(get).toHaveBeenCalledWith('/annonces', { params: { ville: 'tunis' } })
  })

  it('listerToutesLesAnnonces charge toutes les pages par 50', async () => {
    const annonce = (id) => ({ id })
    const get = vi.spyOn(api, 'get').mockImplementation(async (_url, { params }) => ({
      data: {
        items: params.page === 1 ? Array.from({ length: 50 }, (_, i) => annonce(i + 1)) : [annonce(51), annonce(52)],
        page: params.page,
        per_page: 50,
        total: 52,
      },
    }))

    const toutes = await listerToutesLesAnnonces({ statut: 'brouillon' })

    expect(toutes).toHaveLength(52)
    expect(toutes.at(-1)).toEqual({ id: 52 })
    expect(get).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenLastCalledWith('/annonces', { params: { statut: 'brouillon', page: 2, per_page: 50 } })
  })

  it('obtenirHistoriqueAnnonce, listerHistorique et obtenirStatistiques appellent les bonnes routes', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { items: [{ id: 1 }] } })

    await expect(obtenirHistoriqueAnnonce(3)).resolves.toEqual([{ id: 1 }])
    expect(get).toHaveBeenLastCalledWith('/annonces/3/historique')
    await listerHistorique({ action: 'modification', annonce_id: '', page: 2 })
    expect(get).toHaveBeenLastCalledWith('/historique', { params: { action: 'modification', page: 2 } })
    await obtenirStatistiques()
    expect(get).toHaveBeenLastCalledWith('/statistiques')
  })

  it('changerStatut envoie PATCH /annonces/<id>/statut', async () => {
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({ data: { id: 3, statut: 'publiee' } })

    await changerStatut(3, 'publiee')
    expect(patch).toHaveBeenCalledWith('/annonces/3/statut', { statut: 'publiee' })
  })

  it('ajouterPhotos envoie un FormData avec un champ "photos" par fichier', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: [] })
    const fichiers = [new File(['a'], 'a.jpg', { type: 'image/jpeg' }), new File(['b'], 'b.png', { type: 'image/png' })]

    await ajouterPhotos(5, fichiers)
    const [url, corps] = post.mock.calls[0]
    expect(url).toBe('/annonces/5/photos')
    expect(corps.getAll('photos').map((f) => f.name)).toEqual(['a.jpg', 'b.png'])
  })
})

describe('lireErreur', () => {
  it('renvoie les erreurs par champ pour une 400 de validation', () => {
    const erreur = erreurHttp(400, {
      error: 'validation',
      details: { prix_max: ['Doit être supérieur ou égal à prix_min.'], caracteristiques: { 0: ['Trop long.'] } },
    })

    expect(lireErreur(erreur)).toEqual({
      message: 'Certaines données sont invalides.',
      champs: { prix_max: ['Doit être supérieur ou égal à prix_min.'], caracteristiques: ['Trop long.'] },
    })
  })

  it("reprend le message de l'API quand il existe", () => {
    const erreur = erreurHttp(404, { error: 'not_found', message: 'Annonce 999 introuvable' })
    expect(lireErreur(erreur)).toEqual({ message: 'Annonce 999 introuvable', champs: {} })
  })

  it('utilise un message par défaut selon le code HTTP', () => {
    expect(lireErreur(erreurHttp(500, '')).message).toBe('Le serveur a rencontré une erreur. Réessayez plus tard.')
    expect(lireErreur(erreurHttp(418, null)).message).toBe('Erreur inattendue (code 418).')
  })

  it('signale un serveur injoignable (pas de réponse)', () => {
    const erreur = new AxiosError('Network Error', 'ERR_NETWORK')
    expect(lireErreur(erreur).message).toMatch(/Impossible de contacter le serveur/)
  })

  it('signale une requête annulée', () => {
    expect(lireErreur(new CanceledError()).message).toBe('La requête a été annulée.')
  })
})
