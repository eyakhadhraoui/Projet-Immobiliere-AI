import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listerAnnonces, obtenirAnnonce } from '../api/annonces'
import App from '../App'
import FournisseurAuth from '../contexts/FournisseurAuth'
import { PROPRIETAIRE_CONNECTE } from '../test/donnees'

// API simulée : toutes les routes sont des vi.fn(), lireErreur garde son vrai comportement.
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const APPARTEMENT = {
  id: 1,
  titre: 'S+2 meublé à La Marsa',
  type_bien: 'appartement',
  transaction: 'location',
  prix: 1200,
  surface: 85,
  nb_pieces: 3,
  meuble: true,
  ville: 'La Marsa',
  statut: 'publiee',
  photos: [{ id: 7, annonce_id: 1, ordre: 1, url: '/uploads/abc.jpg', type_piece: null }],
}

const VILLA = {
  id: 2,
  titre: 'Villa avec piscine à Hammamet',
  type_bien: 'villa',
  transaction: 'vente',
  prix: 850000,
  surface: 320,
  nb_pieces: 6,
  meuble: false,
  ville: 'Hammamet',
  statut: 'brouillon',
  photos: [],
}

function pageDe(items, { page = 1, total = items.length } = {}) {
  return { items, page, per_page: 12, total }
}

function erreurReseau() {
  return Object.assign(new Error('Network Error'), { isAxiosError: true, response: undefined })
}

/** Affiche l'URL courante pour vérifier la synchronisation des filtres. */
function UrlCourante() {
  const { pathname, search } = useLocation()
  return <span data-testid="url">{pathname + search}</span>
}

// USER-002 : l'en-tête lit la session (FournisseurAuth) ; propriétaire connecté pour que les redirections
// vers /espace/... (tests de routage) affichent les pages de l'espace.
function afficher(url = '/annonces') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <FournisseurAuth utilisateurInitial={PROPRIETAIRE_CONNECTE}>
        <App />
        <UrlCourante />
      </FournisseurAuth>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('Page liste des annonces', () => {
  it('affiche une carte par annonce avec photo, prix, détails et statut', async () => {
    listerAnnonces.mockResolvedValue(pageDe([APPARTEMENT, VILLA]))
    afficher()

    expect(screen.getByRole('status')).toHaveTextContent('Chargement des annonces…')

    const cartes = await screen.findAllByRole('article')
    expect(cartes).toHaveLength(2)

    const premiere = within(cartes[0])
    expect(premiere.getByRole('link', { name: 'S+2 meublé à La Marsa' })).toHaveAttribute('href', '/annonces/1')
    expect(premiere.getByRole('img', { name: 'Photo : S+2 meublé à La Marsa' })).toHaveAttribute('src', '/uploads/abc.jpg')
    expect(premiere.getByText('1 200 TND/mois')).toBeInTheDocument()
    expect(premiere.getByText('La Marsa')).toBeInTheDocument()
    expect(premiere.getByText('85 m²')).toBeInTheDocument()
    expect(premiere.getByText('3 pièces')).toBeInTheDocument()
    expect(premiere.getByText('Appartement · Location')).toBeInTheDocument()
    expect(premiere.getByText('Meublé')).toBeInTheDocument()
    // FRONT-004 : carte publique → badge de transaction au lieu du statut
    expect(premiere.getByText('À louer')).toBeInTheDocument()

    const seconde = within(cartes[1])
    expect(seconde.getByRole('img', { name: 'Aucune photo disponible' })).toBeInTheDocument()
    expect(seconde.getByText('850 000 TND')).toBeInTheDocument()
    expect(seconde.getByText('À vendre')).toBeInTheDocument()

    expect(screen.getByText('Page 1 sur 1 · 2 annonces')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Précédent/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeDisabled()
  })

  it('affiche un message quand la liste est vide', async () => {
    listerAnnonces.mockResolvedValue(pageDe([]))
    afficher('/annonces?ville=Gafsa')

    expect(await screen.findByText('Aucune annonce ne correspond à votre recherche.')).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Effacer les filtres' }))
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/annonces$/)
  })

  it('affiche une erreur et recharge la liste avec le bouton Réessayer', async () => {
    listerAnnonces.mockRejectedValueOnce(erreurReseau()).mockResolvedValueOnce(pageDe([APPARTEMENT]))
    afficher()

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Impossible de contacter le serveur')

    await userEvent.click(within(alerte).getByRole('button', { name: 'Réessayer' }))

    expect(await screen.findAllByRole('article')).toHaveLength(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(listerAnnonces).toHaveBeenCalledTimes(2)
  })

  it('affiche les erreurs par champ renvoyées par une 400 de validation', async () => {
    listerAnnonces.mockRejectedValue({
      isAxiosError: true,
      response: { status: 400, data: { error: 'validation', details: { prix_max: ['Doit être supérieur ou égal à prix_min.'] } } },
    })
    afficher('/annonces?prix_min=500&prix_max=100')

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Certaines données sont invalides.')
    expect(alerte).toHaveTextContent('prix_max : Doit être supérieur ou égal à prix_min.')
  })

  it("appelle l'API avec les filtres et la page lus dans l'URL", async () => {
    listerAnnonces.mockResolvedValue(pageDe([VILLA], { page: 2, total: 13 }))
    afficher('/annonces?ville=tunis&type_bien=villa&meuble=false&page=2')

    await screen.findAllByRole('article')
    expect(listerAnnonces).toHaveBeenCalledWith({
      ville: 'tunis',
      type_bien: 'villa',
      transaction: '',
      prix_min: '',
      prix_max: '',
      meuble: 'false',
      statut: 'publiee', // FRONT-004 : catalogue public = annonces publiées
      page: 2,
      per_page: 12,
    })
    // Les champs de la barre reflètent l'URL (un rafraîchissement garde donc les filtres).
    expect(screen.getByLabelText('Ville')).toHaveValue('tunis')
    expect(screen.getByLabelText('Type de bien')).toHaveValue('villa')
    expect(screen.getByLabelText('Meublé')).toHaveValue('false')
    expect(screen.getByText('Page 2 sur 2 · 13 annonces')).toBeInTheDocument()
  })

  it('permet de demander le classement par compatibilité avec les critères', async () => {
    listerAnnonces.mockResolvedValue(pageDe([APPARTEMENT]))
    afficher('/annonces')
    await screen.findAllByRole('article')

    await userEvent.selectOptions(screen.getByLabelText('Trier les annonces'), 'pertinence')
    await userEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    expect(screen.getByTestId('url')).toHaveTextContent('/annonces?tri=pertinence')
    expect(listerAnnonces).toHaveBeenLastCalledWith(expect.objectContaining({ tri: 'pertinence' }))
  })

  it("écrit les filtres soumis dans l'URL et revient à la page 1", async () => {
    listerAnnonces.mockResolvedValue(pageDe([APPARTEMENT], { page: 3, total: 40 }))
    afficher('/annonces?page=3')
    await screen.findAllByRole('article')

    await userEvent.type(screen.getByLabelText('Ville'), 'Sousse')
    await userEvent.selectOptions(screen.getByLabelText('Transaction'), 'location')
    await userEvent.type(screen.getByLabelText('Prix max (TND)'), '1500')
    await userEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    expect(screen.getByTestId('url')).toHaveTextContent('/annonces?ville=Sousse&transaction=location&prix_max=1500')
    await screen.findAllByRole('article')
    expect(listerAnnonces).toHaveBeenLastCalledWith(
      expect.objectContaining({ ville: 'Sousse', transaction: 'location', prix_max: '1500', page: 1 }),
    )
  })

  it('change de page en gardant les filtres', async () => {
    listerAnnonces.mockResolvedValue(pageDe([APPARTEMENT], { page: 1, total: 30 }))
    afficher('/annonces?ville=tunis')
    await screen.findAllByRole('article')

    expect(screen.getByText('Page 1 sur 3 · 30 annonces')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Suivant/ }))

    expect(screen.getByTestId('url')).toHaveTextContent('/annonces?ville=tunis&page=2')
    await screen.findAllByRole('article')
    expect(listerAnnonces).toHaveBeenLastCalledWith(expect.objectContaining({ ville: 'tunis', page: 2 }))
  })
})

describe('Routage', () => {
  // FRONT-004 : "/" n'est plus une redirection vers /annonces mais la page d'accueil.
  it('affiche la page d\'accueil pour "/"', async () => {
    listerAnnonces.mockResolvedValue(pageDe([]))
    afficher('/')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Trouvez le bien qui vous correspond' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/$/)
  })

  // FRONT-002 : les pages provisoires de FRONT-001 sont remplacées par les vraies pages.
  // FRONT-004 : ces anciennes URL redirigent vers l'espace propriétaire.
  it.each([
    ['/annonces/nouvelle', 'Nouvelle annonce', '/espace/annonces/nouvelle'],
    ['/annonces/4/modifier', "Modifier l'annonce", '/espace/annonces/4/modifier'],
  ])('redirige %s vers la page de l\'espace propriétaire', (url, titre, cible) => {
    obtenirAnnonce.mockReturnValue(new Promise(() => {})) // chargement en cours
    afficher(url)
    expect(screen.getByRole('heading', { level: 1, name: titre })).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent(cible)
    expect(listerAnnonces).not.toHaveBeenCalled()
  })

  it("affiche la page détail de l'annonce pour /annonces/4", async () => {
    obtenirAnnonce.mockResolvedValue({ ...APPARTEMENT, id: 4, description: 'Bel appartement.' })
    afficher('/annonces/4')

    expect(await screen.findByRole('heading', { level: 1, name: 'S+2 meublé à La Marsa' })).toBeInTheDocument()
    expect(obtenirAnnonce).toHaveBeenCalledWith('4')
    expect(listerAnnonces).not.toHaveBeenCalled()
  })

  it('affiche « Page introuvable » pour une adresse inconnue', () => {
    afficher('/adresse/inconnue')
    expect(screen.getByRole('heading', { level: 1, name: 'Page introuvable' })).toBeInTheDocument()
  })
})
