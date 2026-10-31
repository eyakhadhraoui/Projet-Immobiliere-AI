import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ajouterPhotos, creerAnnonce, obtenirAnnonce } from '../api/annonces'
import { obtenirHistoriqueAnnonce } from '../api/historique'
import { estimerPrix } from '../api/ia'
import { afficherApp } from '../test/afficherApp'
import { erreurHttp, fichierImage } from '../test/apiSimulee'
import { STUDIO } from '../test/donnees'

// FRONT-004 : formulaires déplacés dans l'espace propriétaire (/espace/annonces/...) ;
// la fiche affichée après l'enregistrement charge la frise d'historique (API simulée).
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/ia', () => ({ estimerPrix: vi.fn() }))
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const CREEE = { ...STUDIO, id: 42, photos: [] }

async function remplir(user, { transaction = 'location' } = {}) {
  await user.type(screen.getByLabelText('Titre *'), '  Studio centre Tunis ')
  await user.type(screen.getByLabelText('Description *'), 'Proche du métro.')
  await user.selectOptions(screen.getByLabelText('Type de bien *'), 'studio')
  await user.selectOptions(screen.getByLabelText('Transaction *'), transaction)
  await user.type(screen.getByLabelText('Prix (TND) *'), '600')
  await user.type(screen.getByLabelText('Surface (m²) *'), '35')
  await user.type(screen.getByLabelText('Nombre de pièces *'), '1')
  await user.click(screen.getByLabelText('Meublé'))
  await user.type(screen.getByLabelText('Adresse *'), 'Avenue Habib Bourguiba')
  await user.type(screen.getByLabelText('Ville *'), 'Tunis')
  await user.click(screen.getByLabelText('Piscine'))
  await user.click(screen.getByLabelText('Parking'))
}

beforeEach(() => {
  vi.resetAllMocks()
  obtenirHistoriqueAnnonce.mockResolvedValue([])
  obtenirAnnonce.mockResolvedValue(CREEE)
})

describe('Création d\'une annonce', () => {
  it('crée l\'annonce, envoie les photos puis affiche le détail avec un message de succès', async () => {
    const user = userEvent.setup({ delay: null })
    creerAnnonce.mockResolvedValue(CREEE)
    ajouterPhotos.mockResolvedValue({ photos: [] })
    afficherApp('/espace/annonces/nouvelle')

    await remplir(user)
    const photos = [fichierImage('salon.jpg'), fichierImage('cuisine.PNG', 2048, 'image/png')]
    await user.upload(screen.getByLabelText('Ajouter des photos'), photos)
    expect(screen.getByRole('img', { name: 'Aperçu : salon.jpg' })).toHaveAttribute('src', expect.stringMatching(/^blob:/))
    expect(screen.getByRole('img', { name: 'Aperçu : cuisine.PNG' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    expect(await screen.findByText('Annonce créée en brouillon avec 2 photos.')).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/42')
    // USER-002 : plus d'owner_id envoyé, le propriétaire est le compte connecté (côté API).
    expect(creerAnnonce).toHaveBeenCalledWith({
      titre: 'Studio centre Tunis',
      description: 'Proche du métro.',
      type_bien: 'studio',
      transaction: 'location',
      prix: 600,
      surface: 35,
      nb_pieces: 1,
      meuble: true,
      adresse: 'Avenue Habib Bourguiba',
      ville: 'Tunis',
      latitude: null,
      longitude: null,
      caracteristiques: ['parking', 'piscine'],
    })
    expect(ajouterPhotos).toHaveBeenCalledWith(42, photos)
  })

  it('intègre une estimation et ne remplace le prix saisi qu’après confirmation', async () => {
    const user = userEvent.setup({ delay: null })
    estimerPrix.mockResolvedValue({
      prix_estime: 750,
      fourchette: { min: 600, max: 900 },
      transaction: 'location',
      facteurs: [],
      modele: { nom: 'RandomForestRegressor', mape_test: 12.3, entraine_le: '2026-01-01' },
      avertissement: 'Estimation indicative.',
    })
    afficherApp('/espace/annonces/nouvelle')
    await remplir(user)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    expect(await screen.findByText(/Prix estimé/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Utiliser ce prix' }))
    expect(screen.getByLabelText('Prix (TND) *')).toHaveValue(600)
    await user.click(screen.getByRole('button', { name: 'Remplacer le prix' }))
    expect(screen.getByLabelText('Prix (TND) *')).toHaveValue(750)
  })

  it("désactive le bouton pendant l'envoi", async () => {
    const user = userEvent.setup({ delay: null })
    let terminer
    creerAnnonce.mockReturnValue(new Promise((resolve) => (terminer = resolve)))
    afficherApp('/espace/annonces/nouvelle')
    await remplir(user)

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    expect(screen.getByRole('button', { name: 'Envoi en cours…' })).toBeDisabled()
    expect(screen.getByLabelText('Ajouter des photos')).toBeDisabled()
    terminer(CREEE)
    expect(await screen.findByText('Annonce créée en brouillon.')).toBeInTheDocument()
    expect(ajouterPhotos).not.toHaveBeenCalled()
  })

  it("bloque l'envoi et affiche les erreurs de validation côté client", async () => {
    const user = userEvent.setup({ delay: null })
    afficherApp('/espace/annonces/nouvelle')

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    expect(screen.getByRole('alert')).toHaveTextContent('Le formulaire contient des erreurs')
    const titre = screen.getByLabelText('Titre *')
    expect(titre).toHaveAttribute('aria-invalid', 'true')
    expect(titre).toHaveAttribute('aria-describedby', 'aide-titre erreur-titre')
    expect(document.getElementById('erreur-titre')).toHaveTextContent('Champ obligatoire.')
    expect(document.getElementById('erreur-ville')).toHaveTextContent('Champ obligatoire.')
    // Les coordonnées sont facultatives.
    expect(document.getElementById('erreur-latitude')).not.toBeInTheDocument()

    await user.type(titre, 'Abc')
    await user.type(screen.getByLabelText('Prix (TND) *'), '0')
    await user.type(screen.getByLabelText('Surface (m²) *'), '-5')
    await user.type(screen.getByLabelText('Nombre de pièces *'), '-1')
    await user.type(screen.getByLabelText('Latitude (facultative)'), '95')
    await user.type(screen.getByLabelText('Longitude (facultative)'), '-181')
    // Corriger un champ efface son erreur.
    expect(document.getElementById('erreur-titre')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    expect(document.getElementById('erreur-titre')).toHaveTextContent('Doit contenir entre 5 et 150 caractères.')
    expect(document.getElementById('erreur-prix')).toHaveTextContent('Doit être supérieur à 0.')
    expect(document.getElementById('erreur-surface')).toHaveTextContent('Doit être supérieur à 0.')
    expect(document.getElementById('erreur-nb_pieces')).toHaveTextContent('Doit être supérieur ou égal à 0.')
    expect(document.getElementById('erreur-latitude')).toHaveTextContent('Doit être compris entre -90 et 90.')
    expect(document.getElementById('erreur-longitude')).toHaveTextContent('Doit être compris entre -180 et 180.')
    expect(creerAnnonce).not.toHaveBeenCalled()
  })

  it("affiche sous chaque champ les erreurs 400 renvoyées par l'API", async () => {
    const user = userEvent.setup({ delay: null })
    creerAnnonce.mockRejectedValue(
      erreurHttp(400, {
        error: 'validation',
        details: { prix: ['Doit être supérieur à 0.'], owner_id: ['Champ obligatoire.'] },
      }),
    )
    afficherApp('/espace/annonces/nouvelle')
    await remplir(user, { transaction: 'vente' })

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    const erreurPrix = await screen.findByText('Doit être supérieur à 0.')
    expect(erreurPrix).toHaveClass('champ__erreur')
    expect(erreurPrix).toHaveAttribute('id', 'erreur-prix')
    const prix = screen.getByLabelText('Prix (TND) *')
    expect(prix).toHaveAttribute('aria-invalid', 'true')
    expect(prix).toHaveAttribute('aria-describedby', 'erreur-prix')

    // Erreur sur un champ absent du formulaire : affichée en tête.
    const alerte = screen.getByRole('alert')
    expect(alerte).toHaveTextContent('Certaines données sont invalides.')
    expect(alerte).toHaveTextContent('owner_id : Champ obligatoire.')

    expect(screen.getByRole('button', { name: "Créer l'annonce" })).toBeEnabled()
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/nouvelle')
  })

  it("redirige vers le détail avec un avertissement si l'envoi des photos échoue", async () => {
    const user = userEvent.setup({ delay: null })
    creerAnnonce.mockResolvedValue(CREEE)
    ajouterPhotos.mockRejectedValue(
      erreurHttp(400, {
        error: 'validation',
        details: { photos: ["faux.jpg : le fichier n'est pas une image valide (jpg, jpeg, png, webp)."] },
      }),
    )
    afficherApp('/espace/annonces/nouvelle')
    await remplir(user)
    await user.upload(screen.getByLabelText('Ajouter des photos'), fichierImage('faux.jpg'))

    await user.click(screen.getByRole('button', { name: "Créer l'annonce" }))

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(
      "L'annonce a été créée en brouillon, mais les photos n'ont pas pu être envoyées : faux.jpg : le fichier n'est pas une image valide (jpg, jpeg, png, webp). Vous pouvez les ajouter depuis « Modifier ».",
    )
    expect(screen.getByTestId('url')).toHaveTextContent('/espace/annonces/42')
    expect(await screen.findByRole('heading', { level: 1, name: 'Studio centre Tunis' })).toBeInTheDocument()

    // Le message peut être fermé.
    await user.click(within(alerte.parentElement).getByRole('button', { name: 'Fermer le message' }))
    expect(screen.queryByText(/mais les photos n'ont pas pu être envoyées/)).not.toBeInTheDocument()
  })
})
