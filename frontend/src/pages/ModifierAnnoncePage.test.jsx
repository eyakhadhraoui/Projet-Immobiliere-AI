import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ajouterPhotos, modifierAnnonce, obtenirAnnonce, reordonnerPhotos, supprimerPhoto } from '../api/annonces'
import { obtenirHistoriqueAnnonce } from '../api/historique'
import { afficherApp } from '../test/afficherApp'
import { erreurHttp, fichierImage } from '../test/apiSimulee'
import { STUDIO } from '../test/donnees'

// FRONT-004 : formulaires déplacés dans l'espace propriétaire (/espace/annonces/...) ;
// la fiche affichée après l'enregistrement charge la frise d'historique (API simulée).
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })

beforeEach(() => {
  vi.resetAllMocks()
  obtenirHistoriqueAnnonce.mockResolvedValue([])
  obtenirAnnonce.mockResolvedValue(STUDIO)
})

async function afficherFormulaire() {
  afficherApp('/espace/annonces/7/modifier')
  return screen.findByRole('button', { name: 'Enregistrer' })
}

describe("Modification d'une annonce", () => {
  it("préremplit le formulaire avec l'annonce", async () => {
    await afficherFormulaire()

    expect(obtenirAnnonce).toHaveBeenCalledWith('7', true)
    expect(screen.getByLabelText('Titre *')).toHaveValue('Studio centre Tunis')
    expect(screen.getByLabelText('Type de bien *')).toHaveValue('studio')
    expect(screen.getByLabelText('Transaction *')).toHaveValue('location')
    expect(screen.getByLabelText('Prix (TND) *')).toHaveValue(600)
    expect(screen.getByLabelText('Nombre de pièces *')).toHaveValue(1)
    expect(screen.getByLabelText('Meublé')).not.toBeChecked()
    expect(screen.getByLabelText('Internet')).toBeChecked()
    expect(screen.getByLabelText('Parking')).not.toBeChecked()
    expect(screen.getByLabelText('Latitude (facultative)')).toHaveValue(null)
    expect(screen.getAllByRole('img', { name: /^Photo \d de l'annonce$/ })).toHaveLength(3)
  })

  it('envoie uniquement les champs modifiés puis affiche le détail avec un message', async () => {
    const user = utilisateur()
    modifierAnnonce.mockResolvedValue({ ...STUDIO, prix: 650 })
    await afficherFormulaire()

    const prix = screen.getByLabelText('Prix (TND) *')
    await user.clear(prix)
    await user.type(prix, '650')
    await user.click(screen.getByLabelText('Parking'))
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('Annonce modifiée.')).toBeInTheDocument()
    expect(modifierAnnonce).toHaveBeenCalledTimes(1)
    expect(modifierAnnonce).toHaveBeenCalledWith('7', { prix: 650, caracteristiques: ['internet', 'parking'] })
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/7')
    expect(ajouterPhotos).not.toHaveBeenCalled()
  })

  it("n'appelle pas l'API si rien n'a changé", async () => {
    const user = utilisateur()
    await afficherFormulaire()

    // Cocher puis décocher une case ne compte pas comme une modification.
    await user.click(screen.getByLabelText('Jardin'))
    await user.click(screen.getByLabelText('Jardin'))
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText("Aucune modification : l'annonce est inchangée.")).toBeInTheDocument()
    expect(modifierAnnonce).not.toHaveBeenCalled()
  })

  it("affiche sous le champ l'erreur 400 renvoyée par l'API", async () => {
    const user = utilisateur()
    modifierAnnonce.mockRejectedValue(
      erreurHttp(400, { error: 'validation', details: { titre: ['Doit contenir entre 5 et 150 caractères.'] } }),
    )
    await afficherFormulaire()

    await user.type(screen.getByLabelText('Titre *'), ' rénové')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('Doit contenir entre 5 et 150 caractères.')).toHaveAttribute('id', 'erreur-titre')
    expect(screen.getByLabelText('Titre *')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/7/modifier')
  })

  it("envoie les nouvelles photos à l'enregistrement", async () => {
    const user = utilisateur()
    ajouterPhotos.mockResolvedValue({ photos: [] })
    await afficherFormulaire()

    const photo = fichierImage('terrasse.webp', 1024, 'image/webp')
    await user.upload(screen.getByLabelText('Ajouter des photos'), photo)
    expect(screen.getByRole('group', { name: 'Photos (4/10)' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('1 photo ajoutée.')).toBeInTheDocument()
    expect(ajouterPhotos).toHaveBeenCalledWith('7', [photo])
    expect(modifierAnnonce).not.toHaveBeenCalled()
  })

  it('supprime une photo après confirmation', async () => {
    const user = utilisateur()
    supprimerPhoto.mockResolvedValue('')
    await afficherFormulaire()

    // Annuler : rien n'est supprimé.
    await user.click(screen.getByRole('button', { name: 'Supprimer la photo 2' }))
    await user.click(within(screen.getByRole('alertdialog', { name: 'Supprimer cette photo ?' })).getByRole('button', { name: 'Annuler' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(supprimerPhoto).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Supprimer la photo 2' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer la photo' }))

    expect(await screen.findByText('Photo supprimée.')).toBeInTheDocument()
    expect(supprimerPhoto).toHaveBeenCalledWith('7', 12)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    const restantes = screen.getAllByRole('img', { name: /^Photo \d de l'annonce$/ })
    expect(restantes.map((img) => img.getAttribute('src'))).toEqual(['/uploads/a.jpg', '/uploads/c.jpg'])
  })

  it("modifie l'ordre des photos avec les boutons monter / descendre", async () => {
    const user = utilisateur()
    const [a, b, c] = STUDIO.photos
    reordonnerPhotos.mockResolvedValue({ photos: [b, a, c] })
    await afficherFormulaire()

    expect(screen.getByRole('button', { name: 'Monter la photo 1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Descendre la photo 3' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Descendre la photo 1' }))

    expect(await screen.findByText('Ordre des photos enregistré.')).toBeInTheDocument()
    expect(reordonnerPhotos).toHaveBeenCalledWith('7', [12, 11, 13])
    const ordre = screen.getAllByRole('img', { name: /^Photo \d de l'annonce$/ }).map((img) => img.getAttribute('src'))
    expect(ordre).toEqual(['/uploads/b.jpg', '/uploads/a.jpg', '/uploads/c.jpg'])
  })

  it("affiche une page 404 si l'annonce n'existe pas", async () => {
    obtenirAnnonce.mockRejectedValue(erreurHttp(404, { error: 'not_found', message: 'Annonce 7 introuvable' }))
    afficherApp('/espace/annonces/7/modifier')

    expect(await screen.findByRole('heading', { level: 1, name: 'Annonce introuvable' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enregistrer' })).not.toBeInTheDocument()
  })
})
