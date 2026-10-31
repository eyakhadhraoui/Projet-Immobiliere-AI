import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listerAnnonces, obtenirAnnonce } from '../api/annonces'
import { obtenirHistoriqueAnnonce } from '../api/historique'
import { afficherApp } from '../test/afficherApp'
import { STUDIO } from '../test/donnees'

// IA-ANNONCE-001-ROBUSTE : badge prudent calculé par l'API (champ « marche »), affiché sur le site public.
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const PUBLIEE = { ...STUDIO, statut: 'publiee' }
const BONNE_AFFAIRE = { position: 'sous', libelle: 'Bonne affaire', ecart_pourcent: -30 }

beforeEach(() => {
  vi.resetAllMocks()
  obtenirHistoriqueAnnonce.mockResolvedValue([])
})

describe('Badge « marché »', () => {
  it('s’affiche sur les cartes du catalogue, avec l’infobulle « Estimation indicative »', async () => {
    listerAnnonces.mockResolvedValue({
      items: [
        { ...PUBLIEE, id: 1, titre: 'Studio bonne affaire', marche: BONNE_AFFAIRE },
        { ...PUBLIEE, id: 2, titre: 'Studio au prix du marché', marche: { position: 'dans', libelle: 'Prix dans le marché', ecart_pourcent: 2 } },
        { ...PUBLIEE, id: 3, titre: 'Studio cher', marche: { position: 'au_dessus', libelle: 'Prix au-dessus du marché', ecart_pourcent: 45 } },
        // Modèle absent ou confiance faible : l'API renvoie null, aucun badge.
        { ...PUBLIEE, id: 4, titre: 'Studio sans estimation fiable', marche: null },
      ],
      page: 1,
      per_page: 12,
      total: 4,
    })
    afficherApp('/annonces')

    await screen.findByRole('link', { name: 'Studio bonne affaire' })
    const carte = (titre) => screen.getByRole('link', { name: titre }).closest('article')
    const badge = within(carte('Studio bonne affaire')).getByText('Bonne affaire')
    expect(badge).toHaveClass('badge-marche', 'badge-marche--sous')
    expect(badge).toHaveAttribute('data-infobulle', 'Estimation indicative')
    expect(badge).toHaveAttribute('tabindex', '0') // l'infobulle s'ouvre aussi au clavier
    expect(badge).toHaveTextContent('Bonne affaire (estimation indicative)') // lu par les lecteurs d'écran
    expect(within(carte('Studio au prix du marché')).getByText('Prix dans le marché')).toHaveClass('badge-marche--dans')
    expect(within(carte('Studio cher')).getByText('Prix au-dessus du marché')).toHaveClass('badge-marche--au_dessus')
    expect(carte('Studio sans estimation fiable').querySelector('.badge-marche')).toBeNull()
  })

  it('s’affiche sur la fiche publique', async () => {
    obtenirAnnonce.mockResolvedValue({ ...PUBLIEE, marche: BONNE_AFFAIRE })
    afficherApp('/annonces/7')

    expect(await screen.findByText('Bonne affaire')).toHaveAttribute('data-infobulle', 'Estimation indicative')
  })

  it('ne s’affiche pas sur la fiche publique sans estimation fiable', async () => {
    obtenirAnnonce.mockResolvedValue({ ...PUBLIEE, marche: null })
    afficherApp('/annonces/7')

    expect(await screen.findByRole('heading', { level: 1, name: STUDIO.titre })).toBeInTheDocument()
    expect(document.querySelector('.badge-marche')).toBeNull()
  })

  it('n’est pas affiché dans l’espace propriétaire', async () => {
    obtenirAnnonce.mockResolvedValue({ ...PUBLIEE, marche: BONNE_AFFAIRE })
    afficherApp('/espace/annonces/7')

    expect(await screen.findByRole('heading', { level: 1, name: STUDIO.titre })).toBeInTheDocument()
    expect(screen.queryByText('Bonne affaire')).not.toBeInTheDocument()
  })
})
