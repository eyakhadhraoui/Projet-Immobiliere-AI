import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as ragApi from '../api/rag'
import ChatbotRAG from './ChatbotRAG'

vi.mock('../api/rag')

const FAUSSES_CHECKLISTS = {
  location: {
    total: 9,
    titre_fr: 'Checklist — Location',
    titre_ar: 'قائمة الكراء',
    elements: [
      { id: 'cin_proprietaire', nom_fr: 'Pièce d’identité du propriétaire', nom_ar: 'بطاقة التعريف للمالك', obligatoire: true },
      { id: 'contrat_location', nom_fr: 'Contrat de location', nom_ar: 'عقد الكراء', obligatoire: true },
    ],
  },
  vente: {
    total: 10,
    titre_fr: 'Checklist — Vente',
    titre_ar: 'قائمة البيع',
    elements: [
      { id: 'cin_vendeur', nom_fr: 'Pièce d’identité du vendeur', nom_ar: 'بطاقة التعريف للبائع', obligatoire: true },
      { id: 'titre_propriete', nom_fr: 'Titre de propriété (Titre Bleu)', nom_ar: 'الرسم العقاري', obligatoire: true },
    ],
  },
}

const FAUSSES_SUGGESTIONS = [
  { id: 'q1', titre: 'Documents location', question: 'Quels documents pour louer ?', transaction: 'location' },
]

describe('ChatbotRAG', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    ragApi.obtenirChecklists.mockResolvedValue(FAUSSES_CHECKLISTS)
    ragApi.obtenirSuggestions.mockResolvedValue(FAUSSES_SUGGESTIONS)
  })

  it('affiche le message d’accueil en français et permet de basculer en arabe', async () => {
    render(<ChatbotRAG modeFlottant={false} />)

    expect(screen.getByText(/assistant documentaire immobilier pour la Tunisie/i)).toBeInTheDocument()

    // Clic sur le bouton de langue Arabe
    const btnArabe = screen.getByRole('button', { name: /عربي/i })
    await userEvent.click(btnArabe)

    expect(screen.getByText(/مساعدكم القانوني والإجرائي/i)).toBeInTheDocument()
  })

  it('ouvre la checklist interactive et permet de cocher des pièces', async () => {
    render(<ChatbotRAG modeFlottant={false} />)

    await waitFor(() => {
      expect(ragApi.obtenirChecklists).toHaveBeenCalled()
    })

    const btnToggle = screen.getByRole('button', { name: /Checklist interactive/i })
    await userEvent.click(btnToggle)

    expect(screen.getByText('Pièce d’identité du propriétaire')).toBeInTheDocument()
    const caseCin = screen.getByRole('checkbox', { name: /Pièce d’identité du propriétaire/i })
    expect(caseCin).not.toBeChecked()

    await userEvent.click(caseCin)
    expect(caseCin).toBeChecked()
  })

  it('envoie une question et affiche la réponse et les sources citées', async () => {
    ragApi.envoyerMessageRag.mockResolvedValue({
      reponse: 'Pour louer un appartement en Tunisie, le contrat doit être légalisé en municipalité (Baladiya).',
      langue: 'fr',
      transaction: 'location',
      sources: [{ titre: 'Légalisation Baladiya', source: 'Code des Obligations et des Contrats' }],
      audit: null,
    })

    render(<ChatbotRAG modeFlottant={false} />)

    const champSaisie = screen.getByPlaceholderText(/Posez votre question/i)
    await userEvent.type(champSaisie, 'Où légaliser le contrat ?')

    const btnEnvoyer = screen.getByRole('button', { name: /Envoyer/i })
    await userEvent.click(btnEnvoyer)

    await waitFor(() => {
      expect(ragApi.envoyerMessageRag).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Où légaliser le contrat ?',
          transaction: 'location',
        }),
      )
    })

    expect(await screen.findByText(/légalisé en municipalité \(Baladiya\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Légalisation Baladiya/i)).toBeInTheDocument()
  })
})
