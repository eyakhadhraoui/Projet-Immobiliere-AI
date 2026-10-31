import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listerAnnonces, obtenirAnnonce } from '../api/annonces'
import { afficherApp } from '../test/afficherApp'
import { erreurReseau } from '../test/apiSimulee'
import { STUDIO } from '../test/donnees'

vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })
const PUBLIEE = { ...STUDIO, statut: 'publiee' }
const publiees = (n) => Array.from({ length: n }, (_, i) => ({ ...PUBLIEE, id: i + 1, titre: `Annonce publiée ${i + 1}` }))

beforeEach(() => {
  vi.resetAllMocks()
})

describe("Page d'accueil", () => {
  it('affiche la bannière, les 6 dernières annonces publiées et les liens par type', async () => {
    listerAnnonces.mockResolvedValue({ items: publiees(6), page: 1, per_page: 6, total: 9 })
    afficherApp('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Trouvez le bien qui vous correspond' })).toBeInTheDocument()
    const liste = await screen.findByRole('list', { name: 'Dernières annonces publiées' })
    expect(within(liste).getAllByRole('article')).toHaveLength(6)
    expect(within(liste).getByRole('heading', { level: 3, name: 'Annonce publiée 1' })).toBeInTheDocument()
    expect(listerAnnonces).toHaveBeenCalledWith({ statut: 'publiee', page: 1, per_page: 6 })

    expect(screen.getByRole('link', { name: 'Voir toutes les annonces →' })).toHaveAttribute('href', '/annonces')
    expect(screen.getByRole('link', { name: /^Villa/ })).toHaveAttribute('href', '/annonces?type_bien=villa')
    expect(screen.getByRole('link', { name: /^Résidence/ })).toHaveAttribute('href', '/annonces?type_bien=residence')
  })

  it('mène au catalogue filtré depuis la recherche rapide', async () => {
    const user = utilisateur()
    listerAnnonces.mockResolvedValue({ items: [], page: 1, per_page: 6, total: 0 })
    afficherApp('/')
    const recherche = screen.getByRole('search', { name: 'Recherche rapide' })

    await user.type(within(recherche).getByLabelText('Ville'), 'Tunis')
    await user.selectOptions(within(recherche).getByLabelText('Type de bien'), 'villa')
    await user.type(within(recherche).getByLabelText('Budget max (TND)'), '500000')
    await user.click(within(recherche).getByRole('button', { name: 'Rechercher' }))

    expect(screen.getByTestId('url')).toHaveTextContent('/annonces?ville=Tunis&type_bien=villa&prix_max=500000')
    expect(await screen.findByRole('heading', { level: 1, name: 'Annonces' })).toBeInTheDocument()
    expect(listerAnnonces).toHaveBeenLastCalledWith(
      expect.objectContaining({ ville: 'Tunis', type_bien: 'villa', prix_max: '500000', statut: 'publiee', page: 1 }),
    )
    expect(screen.getByLabelText('Ville')).toHaveValue('Tunis')
  })

  it("indique qu'aucune annonce n'est publiée", async () => {
    listerAnnonces.mockResolvedValue({ items: [], page: 1, per_page: 6, total: 0 })
    afficherApp('/')
    expect(await screen.findByText('Aucune annonce publiée pour le moment.')).toBeInTheDocument()
  })

  it('affiche une erreur avec Réessayer', async () => {
    const user = utilisateur()
    listerAnnonces.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce({ items: publiees(1), page: 1, per_page: 6, total: 1 })
    afficherApp('/')

    const alerte = await screen.findByRole('alert')
    await user.click(within(alerte).getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('heading', { level: 3, name: 'Annonce publiée 1' })).toBeInTheDocument()
  })

  it("affiche l'en-tête du site et le pied de page", async () => {
    listerAnnonces.mockResolvedValue({ items: [], page: 1, per_page: 6, total: 0 })
    afficherApp('/')

    const navigation = screen.getByRole('navigation', { name: 'Navigation principale' })
    expect(within(navigation).getByRole('link', { name: 'Accueil' })).toHaveAttribute('aria-current', 'page')
    expect(within(navigation).getByRole('link', { name: 'Annonces' })).toHaveAttribute('href', '/annonces')
    expect(within(navigation).getByRole('link', { name: 'Espace propriétaire' })).toHaveAttribute('href', '/espace')
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Immo Annonces')
    await screen.findByText('Aucune annonce publiée pour le moment.')
  })
})

describe('Fiche publique', () => {
  it("affiche une annonce publiée sans les actions de gestion", async () => {
    obtenirAnnonce.mockResolvedValue(PUBLIEE)
    afficherApp('/annonces/7')

    expect(await screen.findByRole('heading', { level: 1, name: 'Studio centre Tunis' })).toBeInTheDocument()
    expect(screen.getByText('À louer', { selector: '.badge' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Supprimer' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Modifier' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Statut de l'annonce")).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Historique' })).not.toBeInTheDocument()
  })

  it("n'affiche pas une annonce non publiée", async () => {
    obtenirAnnonce.mockResolvedValue(STUDIO) // brouillon
    afficherApp('/annonces/7')

    expect(await screen.findByRole('heading', { level: 1, name: 'Annonce indisponible' })).toBeInTheDocument()
    expect(screen.queryByText('Studio centre Tunis')).not.toBeInTheDocument()
  })
})
