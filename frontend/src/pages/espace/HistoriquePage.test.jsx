import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listerToutesLesAnnonces } from '../../api/annonces'
import { listerHistorique } from '../../api/historique'
import { afficherApp } from '../../test/afficherApp'
import { erreurHttp, erreurReseau } from '../../test/apiSimulee'
import { HISTORIQUE, STUDIO } from '../../test/donnees'

vi.mock('../../api/historique', async () => (await import('../../test/apiSimulee')).simulerApiHistorique())
vi.mock('../../api/annonces', async (importOriginal) =>
  (await import('../../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })
const page = (items, { numero = 1, total = items.length } = {}) => ({ items, page: numero, per_page: 20, total })

beforeEach(() => {
  vi.resetAllMocks()
  listerToutesLesAnnonces.mockResolvedValue([STUDIO, { ...STUDIO, id: 3, titre: 'Maison de vacances Bizerte' }])
})

describe('Page historique', () => {
  it('liste les actions regroupées par jour, avec icône, couleur et détail', async () => {
    listerHistorique.mockResolvedValue(page(HISTORIQUE))
    afficherApp('/espace/historique')

    expect(await screen.findByRole('heading', { level: 2, name: '21 octobre 2026' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: '20 octobre 2026' })).toBeInTheDocument()
    expect(listerHistorique).toHaveBeenCalledWith({
      annonce_id: '', action: '', date_debut: '', date_fin: '', page: 1, per_page: 20,
    })

    const entrees = screen.getAllByRole('article')
    expect(entrees).toHaveLength(5)
    // Exemple du prompt : titre — action : détail — date.
    expect(entrees[0]).toHaveTextContent(
      'Maison de vacances Bizerte — ModifiéePrix 900 → 950 TND ; Meublé Non → Oui21/10/2026 à 12:50',
    )
    expect(entrees.map((e) => e.className)).toEqual([
      'entree entree--modification',
      'entree entree--changement_statut',
      'entree entree--suppression',
      'entree entree--ajout_photos',
      'entree entree--creation',
    ])
    expect(entrees[1]).toHaveTextContent('Statut modifiéBrouillon → Publiée')
    expect(entrees[2]).toHaveTextContent('Villa vendue — SuppriméeStatut : Vendue ; 2 photos supprimées')
    expect(entrees[3]).toHaveTextContent('3 photos ajoutées')
    expect(entrees.every((e) => e.querySelector('svg[aria-hidden="true"]'))).toBe(true)
    expect(screen.getByText('Page 1 sur 1 · 5 actions')).toBeInTheDocument()
  })

  it("applique les filtres, les écrit dans l'URL et revient à la page 1", async () => {
    const user = utilisateur()
    listerHistorique.mockResolvedValue(page(HISTORIQUE, { numero: 2, total: 45 }))
    afficherApp('/espace/historique?page=2')
    await screen.findAllByRole('article')

    await user.selectOptions(await screen.findByLabelText('Annonce'), 'Studio centre Tunis')
    await user.selectOptions(screen.getByLabelText("Type d'action"), 'changement_statut')
    await user.type(screen.getByLabelText('Du'), '2026-10-01')
    await user.type(screen.getByLabelText('Au'), '2026-10-21')
    await user.click(screen.getByRole('button', { name: 'Filtrer' }))

    expect(screen.getByTestId('url')).toHaveTextContent(
      '/espace/historique?annonce_id=7&action=changement_statut&date_debut=2026-10-01&date_fin=2026-10-21',
    )
    await screen.findAllByRole('article')
    expect(listerHistorique).toHaveBeenLastCalledWith({
      annonce_id: '7', action: 'changement_statut', date_debut: '2026-10-01', date_fin: '2026-10-21', page: 1, per_page: 20,
    })
  })

  it("garde dans le filtre une annonce supprimée passée dans l'URL", async () => {
    listerHistorique.mockResolvedValue(page([HISTORIQUE[2]]))
    afficherApp('/espace/historique?annonce_id=5')

    await screen.findAllByRole('article')
    expect(screen.getByLabelText('Annonce')).toHaveDisplayValue('Annonce n° 5')
    expect(listerHistorique).toHaveBeenCalledWith(expect.objectContaining({ annonce_id: '5' }))
  })

  it('passe à la page suivante en gardant les filtres', async () => {
    const user = utilisateur()
    listerHistorique.mockResolvedValue(page(HISTORIQUE, { total: 45 }))
    afficherApp('/espace/historique?action=modification')

    await screen.findByText('Page 1 sur 3 · 45 actions')
    await user.click(screen.getByRole('button', { name: /Suivant/ }))

    expect(screen.getByTestId('url')).toHaveTextContent('/espace/historique?action=modification&page=2')
    await screen.findAllByRole('article')
    expect(listerHistorique).toHaveBeenLastCalledWith(expect.objectContaining({ action: 'modification', page: 2 }))
  })

  it('indique quand aucune action ne correspond', async () => {
    listerHistorique.mockResolvedValue(page([]))
    afficherApp('/espace/historique?action=suppression')

    expect(await screen.findByText('Aucune action ne correspond à ces critères.')).toBeInTheDocument()
  })

  it("affiche les erreurs de validation de l'API", async () => {
    listerHistorique.mockRejectedValue(
      erreurHttp(400, { error: 'validation', details: { date_fin: ['Doit être postérieure ou égale à date_debut.'] } }),
    )
    afficherApp('/espace/historique?date_debut=2026-10-21&date_fin=2026-10-01')

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('date_fin : Doit être postérieure ou égale à date_debut.')
  })

  it('affiche une erreur avec Réessayer', async () => {
    const user = utilisateur()
    listerHistorique.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce(page(HISTORIQUE))
    afficherApp('/espace/historique')

    const alerte = await screen.findByRole('alert')
    await user.click(within(alerte).getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findAllByRole('article')).toHaveLength(5)
  })
})
