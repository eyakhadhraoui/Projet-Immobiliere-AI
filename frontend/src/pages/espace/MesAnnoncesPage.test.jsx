import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { changerStatut, listerToutesLesAnnonces, supprimerAnnonce } from '../../api/annonces'
import { obtenirEtatFiabilite } from '../../api/ia'
import { afficherApp } from '../../test/afficherApp'
import { erreurHttp, erreurReseau } from '../../test/apiSimulee'
import { STUDIO } from '../../test/donnees'

vi.mock('../../api/historique', async () => (await import('../../test/apiSimulee')).simulerApiHistorique())
vi.mock('../../api/annonces', async (importOriginal) =>
  (await import('../../test/apiSimulee')).simulerApi(await importOriginal()),
)
vi.mock('../../api/ia', () => ({
  analyserAnomalieAnnonce: vi.fn(),
  obtenirEtatFiabilite: vi.fn(),
}))

const utilisateur = () => userEvent.setup({ delay: null })

const ANNONCES = [
  { ...STUDIO, id: 1, titre: 'Studio centre Tunis', ville: 'Tunis', prix: 600, statut: 'publiee', updated_at: '2026-10-19T10:00:00+00:00' },
  { ...STUDIO, id: 2, titre: 'Villa avec piscine', ville: 'Hammamet', prix: 850000, transaction: 'vente', statut: 'brouillon', photos: [], updated_at: '2026-10-21T10:00:00+00:00' },
  { ...STUDIO, id: 3, titre: 'Appartement Ariana', ville: 'Ariana', prix: 1100, statut: 'louee', updated_at: '2026-10-20T10:00:00+00:00' },
]

const titresAffiches = () =>
  screen.getAllByRole('row').slice(1).map((ligne) => within(ligne).getByRole('rowheader').textContent)

beforeEach(() => {
  vi.resetAllMocks()
  listerToutesLesAnnonces.mockResolvedValue(ANNONCES)
  obtenirEtatFiabilite.mockResolvedValue({ etat: 'indisponible', libelle: 'Méthode simplifiée (modèle local indisponible)' })
})

async function afficherTableau() {
  afficherApp('/espace/annonces')
  await screen.findByRole('table')
}

describe('Tableau « Mes annonces »', () => {
  it('indique clairement le mode de repli local du contrôle', async () => {
    await afficherTableau()
    expect(await screen.findByRole('status', { name: 'État du contrôle de fiabilité' }))
      .toHaveTextContent('Méthode simplifiée (modèle local indisponible)')
    expect(screen.getByRole('status', { name: 'État du contrôle de fiabilité' }))
      .toHaveTextContent('Les autres vérifications restent actives.')
  })

  it('affiche toutes les annonces, de la plus récemment modifiée à la plus ancienne', async () => {
    await afficherTableau()

    expect(titresAffiches()).toEqual(['Villa avec piscine', 'Appartement Ariana', 'Studio centre Tunis'])
    const ligne = screen.getByRole('row', { name: /Studio centre Tunis/ })
    // Miniature décorative (alt="") : le titre de l'annonce est lu juste à côté.
    expect(ligne.querySelector('.tableau__miniature img')).toHaveAttribute('alt', '')
    expect(ligne.querySelector('.tableau__miniature img')).toHaveAttribute('src', '/uploads/a.jpg')
    expect(within(ligne).getByText('Tunis')).toBeInTheDocument()
    expect(within(ligne).getByText('600 TND/mois')).toBeInTheDocument()
    expect(within(ligne).getByText('Publiée')).toBeInTheDocument()
    expect(within(ligne).getByText('19 octobre 2026')).toBeInTheDocument()
    expect(within(ligne).getByRole('link', { name: 'Voir « Studio centre Tunis »' })).toHaveAttribute('href', '/espace/annonces/1')
    expect(within(ligne).getByRole('link', { name: 'Modifier « Studio centre Tunis »' })).toHaveAttribute(
      'href',
      '/espace/annonces/1/modifier',
    )
    expect(screen.getByText('3 annonces sur 3')).toBeInTheDocument()
  })

  it('recherche dans le titre et la ville, sans tenir compte des accents ni de la casse', async () => {
    const user = utilisateur()
    await afficherTableau()

    await user.type(screen.getByLabelText('Rechercher'), 'HAMMAMÉT')
    expect(titresAffiches()).toEqual(['Villa avec piscine'])
    expect(screen.getByText('1 annonce sur 3')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Rechercher'))
    await user.type(screen.getByLabelText('Rechercher'), 'introuvable')
    expect(screen.getByText('Aucune annonce ne correspond à votre recherche.')).toBeInTheDocument()
  })

  it('filtre par statut', async () => {
    const user = utilisateur()
    await afficherTableau()

    await user.selectOptions(screen.getByLabelText('Statut'), 'brouillon')
    expect(titresAffiches()).toEqual(['Villa avec piscine'])
  })

  it('trie par colonne, puis inverse le sens au second clic', async () => {
    const user = utilisateur()
    await afficherTableau()
    const enTetePrix = () => screen.getByRole('columnheader', { name: /Prix/ })

    expect(enTetePrix()).toHaveAttribute('aria-sort', 'none')
    await user.click(within(enTetePrix()).getByRole('button'))
    expect(enTetePrix()).toHaveAttribute('aria-sort', 'ascending')
    expect(titresAffiches()).toEqual(['Studio centre Tunis', 'Appartement Ariana', 'Villa avec piscine'])

    await user.click(within(enTetePrix()).getByRole('button'))
    expect(enTetePrix()).toHaveAttribute('aria-sort', 'descending')
    expect(titresAffiches()).toEqual(['Villa avec piscine', 'Appartement Ariana', 'Studio centre Tunis'])

    await user.click(within(screen.getByRole('columnheader', { name: /Titre/ })).getByRole('button'))
    expect(titresAffiches()).toEqual(['Appartement Ariana', 'Studio centre Tunis', 'Villa avec piscine'])
  })

  it('publie et dépublie une annonce', async () => {
    const user = utilisateur()
    changerStatut
      .mockResolvedValueOnce({ ...ANNONCES[1], statut: 'publiee' })
      .mockResolvedValueOnce({ ...ANNONCES[0], statut: 'brouillon' })
    await afficherTableau()

    await user.click(screen.getByRole('button', { name: 'Publier « Villa avec piscine »' }))
    expect(await screen.findByText('« Villa avec piscine » est maintenant publiée.')).toBeInTheDocument()
    expect(changerStatut).toHaveBeenLastCalledWith(2, 'publiee')
    const villa = screen.getByRole('row', { name: /Villa avec piscine/ })
    expect(within(villa).getByText('Publiée')).toBeInTheDocument()
    expect(within(villa).getByRole('button', { name: 'Dépublier « Villa avec piscine »' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Dépublier « Studio centre Tunis »' }))
    expect(await screen.findByText(/« Studio centre Tunis » n'est plus publiée/)).toBeInTheDocument()
    expect(changerStatut).toHaveBeenLastCalledWith(1, 'brouillon')
  })

  it('explique qu’une photo détectée doit être remplacée avant publication', async () => {
    const user = utilisateur()
    changerStatut.mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: 'photos_deja_utilisees',
          message: 'Publication bloquée : une photo est déjà utilisée dans une autre annonce. Remplacez-la puis réessayez.',
        },
      },
    })
    await afficherTableau()

    await user.click(screen.getByRole('button', { name: 'Publier « Villa avec piscine »' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Publication bloquée : une photo est déjà utilisée dans une autre annonce. Remplacez-la puis réessayez.',
    )
    expect(screen.getByRole('row', { name: /Villa avec piscine/ })).toHaveTextContent('Brouillon')
  })

  it("affiche l'erreur si la publication échoue", async () => {
    const user = utilisateur()
    changerStatut.mockRejectedValue(erreurHttp(500, ''))
    await afficherTableau()

    await user.click(screen.getByRole('button', { name: 'Publier « Villa avec piscine »' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '« Villa avec piscine » : Le serveur a rencontré une erreur. Réessayez plus tard.',
    )
  })

  it('supprime une annonce après confirmation', async () => {
    const user = utilisateur()
    supprimerAnnonce.mockResolvedValue('')
    await afficherTableau()

    await user.click(screen.getByRole('button', { name: 'Supprimer « Appartement Ariana »' }))
    const fenetre = screen.getByRole('alertdialog', { name: 'Supprimer cette annonce ?' })
    await user.click(within(fenetre).getByRole('button', { name: 'Annuler' }))
    expect(supprimerAnnonce).not.toHaveBeenCalled()
    expect(titresAffiches()).toHaveLength(3)

    await user.click(screen.getByRole('button', { name: 'Supprimer « Appartement Ariana »' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer définitivement' }))

    expect(await screen.findByText("L'annonce « Appartement Ariana » a été supprimée.")).toBeInTheDocument()
    expect(supprimerAnnonce).toHaveBeenCalledWith(3)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(titresAffiches()).toEqual(['Villa avec piscine', 'Studio centre Tunis'])
  })

  it("propose de créer une première annonce quand il n'y en a aucune", async () => {
    listerToutesLesAnnonces.mockResolvedValue([])
    afficherApp('/espace/annonces')

    expect(await screen.findByText("Vous n'avez encore aucune annonce.")).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Créer ma première annonce' })).toHaveAttribute('href', '/espace/annonces/nouvelle')
  })

  it('affiche une erreur avec Réessayer', async () => {
    const user = utilisateur()
    listerToutesLesAnnonces.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce(ANNONCES)
    afficherApp('/espace/annonces')

    const alerte = await screen.findByRole('alert')
    await user.click(within(alerte).getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })
})
