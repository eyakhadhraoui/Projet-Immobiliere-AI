import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { obtenirStatistiques } from '../../api/historique'
import { afficherApp } from '../../test/afficherApp'
import { erreurReseau } from '../../test/apiSimulee'
import { HISTORIQUE } from '../../test/donnees'

vi.mock('../../api/historique', async () => (await import('../../test/apiSimulee')).simulerApiHistorique())
vi.mock('../../api/annonces', async (importOriginal) =>
  (await import('../../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })

const STATISTIQUES = {
  total: 10,
  par_statut: { brouillon: 3, en_attente: 1, publiee: 4, louee: 1, vendue: 1 },
  par_type: { appartement: 5, maison: 2, studio: 1, villa: 2, residence: 0 },
  prix_moyen: { vente: 450000, location: 1250.5 },
  dernieres_actions: HISTORIQUE,
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('Tableau de bord', () => {
  it('affiche les chiffres clés', async () => {
    obtenirStatistiques.mockResolvedValue(STATISTIQUES)
    afficherApp('/espace')

    expect(screen.getByRole('heading', { level: 1, name: 'Tableau de bord' })).toBeInTheDocument()
    await screen.findByText('Annonces par statut')
    const chiffre = (libelle) => screen.getByText(libelle, { selector: '.chiffre__libelle' }).nextElementSibling
    expect(chiffre('Annonces')).toHaveTextContent('10')
    expect(chiffre('Publiées')).toHaveTextContent('4')
    expect(chiffre('Brouillons')).toHaveTextContent('3')
    expect(chiffre('Loyer moyen')).toHaveTextContent(/^1\s250,5\sTND\/mois$/)
    expect(chiffre('Prix de vente moyen')).toHaveTextContent(/^450\s000\sTND$/)
  })

  it('affiche la répartition par statut et par type avec nombres et pourcentages', async () => {
    obtenirStatistiques.mockResolvedValue(STATISTIQUES)
    afficherApp('/espace')

    const parStatut = await screen.findByRole('region', { name: 'Annonces par statut' })
    const lignes = within(parStatut).getAllByRole('listitem')
    expect(lignes.map((l) => l.textContent)).toEqual([
      'Brouillon3 (30 %)',
      'En attente1 (10 %)',
      'Publiée4 (40 %)',
      'Louée1 (10 %)',
      'Vendue1 (10 %)',
    ])
    const parType = screen.getByRole('region', { name: 'Annonces par type de bien' })
    expect(within(parType).getByText('Résidence').parentElement).toHaveTextContent('0 (0 %)')
  })

  it('affiche les dernières actions avec le détail des modifications', async () => {
    obtenirStatistiques.mockResolvedValue(STATISTIQUES)
    afficherApp('/espace')

    const section = await screen.findByRole('region', { name: 'Dernières actions' })
    const entrees = within(section).getAllByRole('article')
    expect(entrees).toHaveLength(5)
    expect(entrees[0]).toHaveTextContent('Maison de vacances Bizerte — Modifiée')
    expect(entrees[0]).toHaveTextContent('Prix 900 → 950 TND ; Meublé Non → Oui')
    expect(entrees[0]).toHaveTextContent('21/10/2026 à 12:50')
    expect(entrees[0]).toHaveClass('entree--modification')
    expect(within(entrees[0]).getByRole('link', { name: 'Maison de vacances Bizerte' })).toHaveAttribute(
      'href',
      '/espace/annonces/3',
    )
    // Annonce supprimée : pas de lien vers une fiche qui n'existe plus.
    expect(within(entrees[2]).queryByRole('link')).not.toBeInTheDocument()
    expect(within(section).getByRole('link', { name: "Voir tout l'historique →" })).toHaveAttribute('href', '/espace/historique')
  })

  it('affiche « — » quand aucun prix moyen ne peut être calculé', async () => {
    obtenirStatistiques.mockResolvedValue({
      ...STATISTIQUES,
      total: 0,
      prix_moyen: { vente: null, location: null },
      dernieres_actions: [],
    })
    afficherApp('/espace')

    await screen.findByText('Aucune action enregistrée pour le moment.')
    expect(screen.getByText('Loyer moyen', { selector: '.chiffre__libelle' }).nextElementSibling).toHaveTextContent('—')
  })

  it('affiche une erreur avec Réessayer', async () => {
    const user = utilisateur()
    obtenirStatistiques.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce(STATISTIQUES)
    afficherApp('/espace')

    const alerte = await screen.findByRole('alert')
    await user.click(within(alerte).getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('region', { name: 'Annonces par statut' })).toBeInTheDocument()
  })
})

describe("Menu de l'espace propriétaire", () => {
  it('indique la page active et se replie derrière un bouton', async () => {
    const user = utilisateur()
    obtenirStatistiques.mockResolvedValue(STATISTIQUES)
    afficherApp('/espace')

    const menu = screen.getByRole('navigation', { name: 'Espace propriétaire' })
    expect(within(menu).getByRole('link', { name: 'Tableau de bord' })).toHaveAttribute('aria-current', 'page')
    expect(within(menu).getByRole('link', { name: 'Mes annonces' })).not.toHaveAttribute('aria-current')
    expect(within(menu).getByRole('link', { name: 'Historique' })).toHaveAttribute('href', '/espace/historique')

    const bouton = screen.getByRole('button', { name: "Menu de l'espace" })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    await user.click(bouton)
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    expect(menu).toHaveAttribute('data-ouvert', 'true')
    await screen.findByRole('region', { name: 'Annonces par statut' })
  })
})
