import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ameliorerDescriptionReclamation, analyserAssistantReclamation, listerReclamations } from '../../api/reclamations'
import { afficherApp } from '../../test/afficherApp'

vi.mock('../../api/reclamations', () => ({
  ameliorerDescriptionReclamation: vi.fn(),
  analyserAssistantReclamation: vi.fn(),
  listerReclamations: vi.fn(),
  modifierReclamation: vi.fn(),
  supprimerReclamation: vi.fn(),
  ajouterMessageReclamation: vi.fn(),
  creerReclamation: vi.fn(),
}))
vi.mock('../../api/annonces', async (importOriginal) => ({
  ...(await importOriginal()),
  listerAnnonces: vi.fn().mockResolvedValue({ items: [] }),
}))

const reclamation = {
  id: 7, reference: 'REC-2026-0007', user_id: 2, annonce_id: 3,
  titre_annonce: 'Appartement à Tunis', type: 'fausse_annonce',
  objet: 'Prix incohérent', description: 'Le prix affiché est différent.',
  priorite: 'haute', statut: 'nouvelle', date_creation: '2026-10-26T08:00:00Z',
  pieces_jointes: [], messages: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  listerReclamations.mockResolvedValue({ items: [reclamation], total: 1 })
  analyserAssistantReclamation.mockResolvedValue({
    motif_suggere: 'prix_incorrect',
    priorite_suggeree: 'normale',
    raison_priorite: 'Suggestion de classement.',
    pieces_a_fournir: ['Capture du prix affiché'],
    conseil: 'Vérifiez les informations avant toute action.',
    mention: 'Suggestions indicatives; la décision finale appartient au modérateur.',
    brouillon_reponse: 'Bonjour, nous avons bien reçu votre signalement.',
    signalements_recents_meme_proprietaire: 0,
    annonces_similaires: [],
    doublon_possible: false,
  })
  ameliorerDescriptionReclamation.mockResolvedValue({
    description: 'Je souhaite signaler une différence de prix.',
    mention: 'Proposition à relire.',
  })
})

describe('Gestion des réclamations', () => {
  it('affiche les badges de type, priorité, statut et la pastille du menu', async () => {
    afficherApp('/espace/reclamations')

    expect(await screen.findByText('Fausse annonce', { selector: 'span.reclamation__type' })).toHaveClass('reclamation__type')
    expect(screen.getByText('Haute', { selector: 'span.reclamation__badge' })).toHaveClass('reclamation__badge--haute')
    expect(screen.getByText('Nouvelle', { selector: 'span.reclamation__badge' })).toHaveClass('reclamation__badge--nouvelle')
    expect(screen.getByLabelText('1 nouvelles réclamations')).toBeInTheDocument()
  })

  it('propose le formulaire avec priorité, compteur et panneau assistant', async () => {
    const user = userEvent.setup({ delay: null })
    afficherApp('/espace/reclamations')
    await screen.findByText('Prix incohérent')
    await user.click(screen.getByRole('button', { name: '+ Nouvelle réclamation' }))

    expect(screen.getByRole('group', { name: 'Priorité' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Pièces jointes/)).toHaveAttribute('accept', expect.stringContaining('application/pdf'))
    const description = screen.getByLabelText('Description')
    await user.type(description, 'Le montant diffère.')
    expect(screen.getByText('19 / 1000 caractères')).toBeInTheDocument()
    expect(await screen.findByText('Motif suggéré')).toBeInTheDocument()
  })

  it('génère une proposition distincte puis la reprend seulement après validation', async () => {
    const user = userEvent.setup({ delay: null })
    afficherApp('/espace/reclamations')
    await screen.findByText('Prix incohérent')
    await user.click(screen.getByRole('button', { name: '+ Nouvelle réclamation' }))
    await user.type(screen.getByLabelText('Objet'), 'Prix modifié')

    await user.click(screen.getByRole('button', { name: 'Générer une description avec Gemini' }))

    expect(ameliorerDescriptionReclamation).toHaveBeenCalledWith({ objet: 'Prix modifié', description: '' })
    expect(await screen.findByText('Je souhaite signaler une différence de prix.')).toBeInTheDocument()
    const champDescription = screen.getByLabelText('Description')
    expect(champDescription).toHaveValue('')

    await user.click(screen.getByRole('button', { name: 'Utiliser cette proposition' }))

    expect(champDescription).toHaveValue('Je souhaite signaler une différence de prix.')
    expect(screen.getByRole('button', { name: 'Améliorer la description avec Gemini' })).toBeInTheDocument()
  })
})
