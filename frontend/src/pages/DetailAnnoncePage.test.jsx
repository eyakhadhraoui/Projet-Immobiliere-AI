import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { changerStatut, listerToutesLesAnnonces, obtenirAnnonce, obtenirFiabiliteAnnonce, supprimerAnnonce } from '../api/annonces'
import { obtenirHistoriqueAnnonce } from '../api/historique'
import { afficherApp } from '../test/afficherApp'
import { erreurHttp, erreurReseau } from '../test/apiSimulee'
import { HISTORIQUE, STUDIO } from '../test/donnees'

vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })

beforeEach(() => {
  vi.resetAllMocks()
  obtenirAnnonce.mockResolvedValue(STUDIO)
  obtenirFiabiliteAnnonce.mockResolvedValue({ controle: null, motif_attente: null, revue_demandee_le: null })
  listerToutesLesAnnonces.mockResolvedValue([])
  obtenirHistoriqueAnnonce.mockResolvedValue([])
})

// FRONT-004 : la fiche avec les actions de gestion est maintenant dans l'espace propriétaire
// (/espace/annonces/:id) ; /annonces/:id est la fiche publique, sans actions.

async function afficherDetail() {
  afficherApp('/espace/annonces/7')
  return screen.findByRole('heading', { level: 1, name: 'Studio centre Tunis' })
}

describe("Détail d'une annonce", () => {
  it('affiche toutes les informations, les caractéristiques et le badge de statut', async () => {
    await afficherDetail()

    expect(screen.getByText('Brouillon', { selector: '.badge' })).toBeInTheDocument()
    expect(screen.getByText('600 TND/mois')).toBeInTheDocument()
    expect(screen.getByText('Avenue Habib Bourguiba, Tunis')).toBeInTheDocument()
    expect(screen.getByText('Studio')).toBeInTheDocument()
    expect(screen.getByText('35 m²')).toBeInTheDocument()
    expect(screen.getByText('1 pièce')).toBeInTheDocument()
    expect(screen.getByText('Non')).toBeInTheDocument()
    expect(screen.getByText('Internet')).toBeInTheDocument()
    expect(screen.getByText(/Proche du métro\./)).toBeInTheDocument()
    expect(screen.getByText('20 octobre 2026')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Modifier' })).toHaveAttribute('href', '/espace/annonces/7/modifier')
  })

  it('affiche le panneau de fiabilité dans le détail propriétaire', async () => {
    obtenirFiabiliteAnnonce.mockResolvedValue({
      controle: {
        niveau: 'a_surveiller',
        score: 42,
        decision: 'confirmation_requise',
        raisons: [{ type: 'texte', signal: 'description_proche', texte: 'La description ressemble à une annonce publique.' }],
      },
      motif_attente: null,
      revue_demandee_le: null,
    })
    await afficherDetail()

    expect(await screen.findByRole('heading', { level: 2, name: 'Vérification automatique' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Avant de publier votre annonce' })).toBeInTheDocument()
    expect(screen.getByText('La description ressemble à une annonce publique.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Publier quand même' })).toBeInTheDocument()
  })

  it('bloque la confirmation lorsqu’une photo doit être remplacée', async () => {
    obtenirFiabiliteAnnonce.mockResolvedValue({
      controle: {
        niveau: 'a_verifier',
        score: 60,
        decision: 'mise_en_attente',
        raisons: [{ type: 'photo', signal: 'photos_communes', texte: 'Une photo est déjà utilisée dans une autre annonce.' }],
      },
      motif_attente: null,
      revue_demandee_le: null,
    })
    await afficherDetail()

    expect(await screen.findByRole('link', { name: 'Remplacer ces photos' })).toHaveAttribute(
      'href', '/espace/annonces/7/modifier',
    )
    expect(screen.queryByRole('button', { name: 'Publier quand même' })).not.toBeInTheDocument()
  })

  it('confirme la publication d’un signal modéré depuis le panneau de fiabilité', async () => {
    const user = utilisateur()
    obtenirFiabiliteAnnonce.mockResolvedValue({
      controle: {
        niveau: 'a_surveiller',
        score: 42,
        decision: 'confirmation_requise',
        raisons: [{ type: 'prix', signal: 'ecart_estimation', texte: 'Le prix diffère de l’estimation.' }],
      },
      motif_attente: null,
      revue_demandee_le: null,
    })
    changerStatut.mockResolvedValue({ ...STUDIO, statut: 'publiee' })
    await afficherDetail()
    await user.click(await screen.findByRole('button', { name: 'Publier quand même' }))

    expect(changerStatut).toHaveBeenCalledWith(7, 'publiee', true)
    expect(await screen.findByText(/Votre annonce est publiée/)).toBeInTheDocument()
  })

  it("affiche la frise de l'historique de l'annonce", async () => {
    const etapes = HISTORIQUE.filter((entree) => entree.annonce_id === 7)
    obtenirHistoriqueAnnonce.mockResolvedValue(etapes)
    await afficherDetail()

    const frise = await screen.findByRole('list', { name: "Actions sur l'annonce" })
    const entrees = within(frise).getAllByRole('article')
    expect(obtenirHistoriqueAnnonce).toHaveBeenCalledWith(7)
    // Montants avec espaces insécables : on compare avec des espaces normales.
    expect(entrees.map((e) => e.textContent.replace(/\s/g, ' '))).toEqual([
      'Statut modifiéBrouillon → Publiée21/10/2026 à 09:15',
      'Photos ajoutées3 photos ajoutées20/10/2026 à 10:00',
      'CrééeStudio · Location · 600 TND/mois · Tunis20/10/2026 à 09:00',
    ])
    expect(screen.getByRole('link', { name: "Voir dans l'historique complet" })).toHaveAttribute(
      'href',
      '/espace/historique?annonce_id=7',
    )
  })

  it('recharge la frise après un changement de statut', async () => {
    const user = utilisateur()
    changerStatut.mockResolvedValue({ ...STUDIO, statut: 'publiee', updated_at: '2026-10-21T13:00:00+00:00' })
    await afficherDetail()
    await screen.findByText('Aucune action enregistrée pour cette annonce.')

    await user.selectOptions(screen.getByLabelText("Statut de l'annonce"), 'publiee')
    await user.click(screen.getByRole('button', { name: 'Changer le statut' }))

    await screen.findByText('Statut modifié : Publiée.')
    await screen.findByText('Aucune action enregistrée pour cette annonce.')
    expect(obtenirHistoriqueAnnonce).toHaveBeenCalledTimes(2)
  })

  it('change la photo principale au clic sur une miniature', async () => {
    const user = utilisateur()
    await afficherDetail()

    const principale = screen.getByRole('img', { name: 'Studio centre Tunis — photo 1 sur 3' })
    expect(principale).toHaveAttribute('src', '/uploads/a.jpg')
    expect(screen.getByRole('button', { name: 'Afficher la photo 1' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: 'Afficher la photo 3' }))

    expect(screen.getByRole('img', { name: 'Studio centre Tunis — photo 3 sur 3' })).toHaveAttribute('src', '/uploads/c.jpg')
    expect(screen.getByRole('button', { name: 'Afficher la photo 3' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Afficher la photo 1' })).toHaveAttribute('aria-pressed', 'false')
  })

  it("affiche l'image de remplacement sans photo", async () => {
    obtenirAnnonce.mockResolvedValue({ ...STUDIO, photos: [] })
    await afficherDetail()
    expect(screen.getByRole('img', { name: 'Aucune photo disponible' })).toBeInTheDocument()
  })

  it('change le statut avec le menu', async () => {
    const user = utilisateur()
    changerStatut.mockResolvedValue({ ...STUDIO, statut: 'publiee' })
    await afficherDetail()

    const bouton = screen.getByRole('button', { name: 'Changer le statut' })
    expect(bouton).toBeDisabled() // statut inchangé
    await user.selectOptions(screen.getByLabelText("Statut de l'annonce"), 'publiee')
    await user.click(bouton)

    expect(await screen.findByText('Statut modifié : Publiée.')).toBeInTheDocument()
    expect(changerStatut).toHaveBeenCalledWith(7, 'publiee')
    expect(screen.getByText('Publiée', { selector: '.badge' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Changer le statut' })).toBeDisabled()
  })

  it("affiche l'erreur si le changement de statut échoue", async () => {
    const user = utilisateur()
    changerStatut.mockRejectedValue(erreurHttp(500, ''))
    await afficherDetail()

    await user.selectOptions(screen.getByLabelText("Statut de l'annonce"), 'louee')
    await user.click(screen.getByRole('button', { name: 'Changer le statut' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Le serveur a rencontré une erreur. Réessayez plus tard.')
    expect(screen.getByText('Brouillon', { selector: '.badge' })).toBeInTheDocument()
  })

  it('supprime après confirmation puis revient à la liste avec un message', async () => {
    const user = utilisateur()
    supprimerAnnonce.mockResolvedValue('')
    await afficherDetail()

    // Annuler ferme la fenêtre sans supprimer.
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    const fenetre = screen.getByRole('alertdialog', { name: 'Supprimer cette annonce ?' })
    expect(fenetre).toHaveTextContent("L'annonce « Studio centre Tunis » et ses photos seront définitivement supprimées.")
    expect(within(fenetre).getByRole('button', { name: 'Annuler' })).toHaveFocus()
    await user.click(within(fenetre).getByRole('button', { name: 'Annuler' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()

    // Échap ferme aussi la fenêtre.
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(supprimerAnnonce).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer définitivement' }))

    expect(await screen.findByText("L'annonce « Studio centre Tunis » a été supprimée.")).toBeInTheDocument()
    expect(supprimerAnnonce).toHaveBeenCalledWith(7)
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/espace\/annonces$/)
    expect(await screen.findByRole('heading', { level: 1, name: 'Mes annonces' })).toBeInTheDocument()
  })

  it('garde la fenêtre ouverte avec un message si la suppression échoue', async () => {
    const user = utilisateur()
    supprimerAnnonce.mockRejectedValue(erreurReseau())
    await afficherDetail()

    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer définitivement' }))

    const fenetre = screen.getByRole('alertdialog')
    expect(await within(fenetre).findByRole('alert')).toHaveTextContent('Impossible de contacter le serveur')
    expect(within(fenetre).getByRole('button', { name: 'Supprimer définitivement' })).toBeEnabled()
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/7')
  })

  it("affiche une page 404 si l'annonce n'existe pas", async () => {
    obtenirAnnonce.mockRejectedValue(erreurHttp(404, { error: 'not_found', message: 'Annonce 999 introuvable' }))
    afficherApp('/espace/annonces/999')

    expect(await screen.findByRole('heading', { level: 1, name: 'Annonce introuvable' })).toBeInTheDocument()
    expect(screen.getByText("L'annonce n° 999 n'existe pas ou a été supprimée.")).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← Retour à mes annonces' })).toHaveAttribute('href', '/espace/annonces')
  })

  it('affiche une erreur et recharge avec Réessayer', async () => {
    const user = utilisateur()
    obtenirAnnonce.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce(STUDIO)
    afficherApp('/espace/annonces/7')

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Impossible de contacter le serveur')
    await user.click(within(alerte).getByRole('button', { name: 'Réessayer' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Studio centre Tunis' })).toBeInTheDocument()
    expect(obtenirAnnonce).toHaveBeenCalledTimes(2)
  })
})
