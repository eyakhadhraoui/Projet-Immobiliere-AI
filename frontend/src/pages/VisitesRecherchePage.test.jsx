import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VisitesRecherchePage from './VisitesRecherchePage'

const { rechercherVisites, creerVisite } = vi.hoisted(() => ({
  rechercherVisites: vi.fn(),
  creerVisite: vi.fn(),
}))

vi.mock('../api/visites', () => ({ rechercherVisites, creerVisite }))
vi.mock('../hooks/useAuth', () => ({ useAuth: () => ({ utilisateur: null }) }))

const RESULTAT = {
  recherche_id: 12,
  total: 1,
  tri_applique: 'chronologique',
  methode_classement: 'chronologique_repli',
  message_classement: 'Classement par date; le modèle LightGBM n’a pas été utilisé.',
  items: [{
    id: 4,
    titre: 'Appartement S+2 à La Marsa',
    ville: 'La Marsa',
    surface: 85,
    nb_pieces: 3,
    prix: 1200,
    transaction: 'location',
    creneaux_compatibles: [{
      debut: '2030-03-02T09:00:00', date: '2030-03-02', heure_debut: '09:00', heure_fin: '09:30',
    }],
  }],
}

describe('Recherche de visites', () => {
  beforeEach(() => {
    rechercherVisites.mockReset()
    creerVisite.mockReset()
  })

  it('envoie les critères et les disponibilités au serveur puis affiche les créneaux compatibles', async () => {
    rechercherVisites.mockResolvedValue(RESULTAT)
    render(<MemoryRouter><VisitesRecherchePage /></MemoryRouter>)

    await userEvent.type(screen.getByLabelText('Ville(s), séparées par des virgules'), 'Tunis')
    await userEvent.click(screen.getByRole('button', { name: 'Rechercher les visites' }))

    expect(rechercherVisites).toHaveBeenCalledWith(expect.objectContaining({
      villes: ['Tunis'], transaction: 'location',
      disponibilites: [expect.objectContaining({ debut: expect.stringMatching(/T09:00:00$/) })],
    }))
    expect(await screen.findByRole('heading', { name: 'Appartement S+2 à La Marsa' })).toBeInTheDocument()
    expect(screen.getByText(/09:00–09:30/)).toBeInTheDocument()
    expect(screen.getByText(/modèle LightGBM n’a pas été utilisé/)).toBeInTheDocument()
  })

  it('relie la demande de visite à la recherche et au créneau sélectionné', async () => {
    rechercherVisites.mockResolvedValue(RESULTAT)
    creerVisite.mockResolvedValue({ id: 33 })
    render(<MemoryRouter><VisitesRecherchePage /></MemoryRouter>)
    await userEvent.type(screen.getByLabelText('Téléphone de contact pour la demande'), '20123456')
    await userEvent.click(screen.getByRole('button', { name: 'Rechercher les visites' }))
    await screen.findByRole('heading', { name: 'Appartement S+2 à La Marsa' })
    await userEvent.click(screen.getByRole('button', { name: 'Demander ce créneau' }))

    expect(creerVisite).toHaveBeenCalledWith(expect.objectContaining({
      annonce_id: 4, recherche_id: 12, date_visite: '2030-03-02',
      heure_debut: '09:00', heure_fin: '09:30', telephone_contact: '20123456',
    }))
    expect(await screen.findByText(/Votre demande de visite a été envoyée/)).toBeInTheDocument()
  })

  it('permet de retirer une plage de disponibilité ajoutée', async () => {
    render(<MemoryRouter><VisitesRecherchePage /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter une disponibilité' }))
    expect(screen.getAllByLabelText('Date')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'Retirer la disponibilité 2' }))
    expect(screen.getAllByLabelText('Date')).toHaveLength(1)
  })
})
