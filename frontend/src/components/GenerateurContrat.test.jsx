import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as ragApi from '../api/rag'
import GenerateurContrat from './GenerateurContrat'

vi.mock('../api/rag')

const FAUX_CONTRAT_REP = {
  type_contrat: 'location',
  langue: 'fr',
  contrat_markdown: '# CONTRAT DE BAIL À USAGE D\'HABITATION\n\nEntre M. Mohamed Ben Salem et Mlle Nour Trabelsi...',
}

describe('GenerateurContrat', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    ragApi.genererContrat.mockResolvedValue(FAUX_CONTRAT_REP)
  })

  it('affiche le formulaire pré-rempli et permet de générer un contrat', async () => {
    render(<GenerateurContrat />)

    expect(screen.getByText(/Générateur de projet de contrat conforme/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Mohamed Ben Salem')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Nour Trabelsi')).toBeInTheDocument()

    const btnGenerer = screen.getByRole('button', { name: /Générer le projet de contrat/i })
    await userEvent.click(btnGenerer)

    await waitFor(() => {
      expect(ragApi.genererContrat).toHaveBeenCalledWith(
        expect.objectContaining({
          type_contrat: 'location',
          langue: 'fr',
          bailleur: expect.objectContaining({ nom_complet: 'Mohamed Ben Salem' }),
        }),
      )
    })

    expect(await screen.findByTestId('apercu-contrat')).toBeInTheDocument()
    expect(screen.getByText(/CONTRAT DE BAIL À USAGE D'HABITATION/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copier/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Télécharger/i })).toBeInTheDocument()
  })

  it('permet de changer pour une promesse de vente et de passer en langue arabe', async () => {
    render(<GenerateurContrat />)

    const btnVente = screen.getByRole('button', { name: /Promesse de vente/i })
    await userEvent.click(btnVente)

    const btnArabe = screen.getByRole('button', { name: /العربية/i })
    await userEvent.click(btnArabe)

    expect(screen.getByText(/توليد مشروع عقد قانوني تونسي/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /إنشاء مشروع العقد الرسمي/i })).toBeInTheDocument()
  })
})
