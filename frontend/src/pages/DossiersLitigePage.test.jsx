import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import * as api from '../api/dossiersLitige'
import DossiersLitigePage from './DossiersLitigePage'

vi.mock('../api/dossiersLitige')

const DOSSIER = {
  id: 'dossier-1', case_id: 'dossier-1', nom: 'Retenue sur le dépôt', titre: 'Retenue sur le dépôt',
  cree_le: '2026-10-26T10:00:00+01:00', description: 'Analyse factuelle',
  documents: [{ id: 1, nom: 'reponse_locataire.txt', titre: 'Réponse du locataire', role_auteur: 'tenant', passages: [
    { id: 'chunk-1', chunk_id: 'chunk-1', texte: 'Je conteste la retenue sur le sol.', types: ['party_statement'], sujets: ['deposit'], dates: ['2026-10-20'], auteur_attribue: 'tenant', role_auteur: 'tenant' },
  ] }],
}

describe('DossiersLitigePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.listerDossiersLitige.mockResolvedValue([{
      ...DOSSIER, documents: [{ id: 1, nom: 'reponse_locataire.txt', titre: 'Réponse du locataire', role_auteur: 'tenant', passages: [] }],
    }])
    api.obtenirDossierLitige.mockResolvedValue(DOSSIER)
    api.obtenirConfigurationLitige.mockResolvedValue({ local_only: true, semantic_model_available: false, limits: [] })
    api.obtenirPreuvesLitige.mockResolvedValue({ items: [
      { chunk_id: 'chunk-1', nom_fichier: 'reponse_locataire.txt', texte: 'Je conteste la retenue sur le sol.', type_preuve: 'party_statement', sujet: 'deposit', score_classification: 0.7, debut: 0, fin: 34 },
    ] })
    api.obtenirChronologieLitige.mockResolvedValue({ items: [
      { date: '2026-10-20', quote: 'Je conteste la retenue.', source: 'reponse_locataire.txt', verified: false },
    ] })
    api.obtenirComptesLitige.mockResolvedValue({ items: {
      tenant: [{ chunk_id: 'chunk-1', text: 'Je conteste la retenue.', source: 'reponse_locataire.txt', status: 'déclaration non authentifiée' }],
      landlord: [],
    } })
    api.obtenirContradictionsLitige.mockResolvedValue({ items: [] })
    api.obtenirPreuvesNonIdentifiees.mockResolvedValue({ items: [] })
    api.obtenirRapportLitige.mockResolvedValue({ timeline: [], retrieved_passages: [], legal_warning: 'Pas un conseil juridique.' })
    api.rechercherPreuvesLitige.mockResolvedValue({ mode: 'tfidf_local', items: [
      { chunk_id: 'chunk-1', nom_fichier: 'reponse_locataire.txt', texte: 'Je conteste la retenue sur le sol.', score: 0.75 },
    ] })
    api.poserQuestionLitige.mockResolvedValue({
      answer_status: 'supported', answer: 'Passage retrouvé.', value: null,
      citations: [{ chunk_id: 'chunk-1', quote: 'Je conteste la retenue sur le sol.' }],
    })
  })

  it('affiche les documents et les vues des parties et de la chronologie', async () => {
    render(<MemoryRouter><DossiersLitigePage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: 'Retenue sur le dépôt' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Documents' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText('Je conteste la retenue sur le sol.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Réponse du locataire' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: 'Comptes des parties' }))
    expect(await screen.findByText('Je conteste la retenue.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Chronologie' }))
    expect(await screen.findByText('20/10/2026')).toBeInTheDocument()
  })

  it('affiche les passages trouvés et une réponse avec citation', async () => {
    render(<MemoryRouter><DossiersLitigePage /></MemoryRouter>)
    await screen.findByRole('heading', { name: 'Retenue sur le dépôt' })
    await userEvent.click(screen.getByRole('tab', { name: 'Recherche et questions' }))
    await userEvent.type(screen.getByLabelText('Question sur les documents'), 'retenue sol')
    await userEvent.click(screen.getByRole('button', { name: 'Rechercher les passages' }))

    expect(await screen.findByText('Je conteste la retenue sur le sol.')).toBeInTheDocument()
    expect(api.rechercherPreuvesLitige).toHaveBeenCalledWith('dossier-1', 'retenue sol')
    await userEvent.click(screen.getByRole('button', { name: 'Obtenir une réponse sourcée' }))
    expect(await screen.findByText('Passage retrouvé.')).toBeInTheDocument()
    expect(api.poserQuestionLitige).toHaveBeenCalledWith('dossier-1', 'retenue sol')
  })
})
