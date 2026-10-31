import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as ragApi from '../api/rag'
import AnalyseurDocument from './AnalyseurDocument'

vi.mock('../api/rag')

const FAUX_RAPPORT = {
  statut_document: 'a_completer',
  transaction: 'location',
  pagination: {
    total_physique: 2,
    total_annonce: 3,
    numeros_detectes: [1, 3],
    sauts_numerotation: [2],
    pages_vides: [],
    alertes: ['Saut de numérotation : page 2 manquante'],
    pagination_conforme: false,
  },
  champs_extraits: {
    type_transaction: 'location',
    montants_trouves: ['850'],
    dates_trouvees: ['15/09/2026'],
    cins_trouvees: ['08765432', '11223344'],
    mentions_signature: ['signature', 'baladiya'],
    signature_detectee: true,
    annexes_citees: ['Annexe 1'],
    nb_champs_vides: 1,
  },
  alertes: [
    'Saut de numérotation : page 2 manquante',
    '1 champ non renseigné détecté',
  ],
  audit_checklist: {
    elements_fournis: ['cin_proprietaire', 'cin_locataire', 'loyer_et_caution'],
    elements_manquants: [{ id: 'titre_propriete', nom_fr: 'Justificatif de propriété' }],
    pourcentage_completude: 33,
  },
  recommandations_diwan: [
    'Enregistrer le document à la Recette des finances dans les 60 jours.',
  ],
}

describe('AnalyseurDocument', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    ragApi.analyserDocument.mockResolvedValue(FAUX_RAPPORT)
  })

  it('affiche la zone de dépôt PDF et permet de basculer en saisie de texte', async () => {
    render(<AnalyseurDocument />)

    expect(screen.getByText(/Analyse et audit documentaire/i)).toBeInTheDocument()
    expect(screen.getByText(/Parcourir un fichier PDF/i)).toBeInTheDocument()

    const btnTexte = screen.getByRole('button', { name: /Texte du contrat/i })
    await userEvent.click(btnTexte)

    expect(screen.getByPlaceholderText(/Collez ici le texte/i)).toBeInTheDocument()
  })

  it('charge un exemple, lance l’analyse et affiche le rapport détaillé', async () => {
    const callbackChecklist = vi.fn()
    render(<AnalyseurDocument onChecklistMiseAJour={callbackChecklist} />)

    // Basculer en mode texte
    const btnTexte = screen.getByRole('button', { name: /Texte du contrat/i })
    await userEvent.click(btnTexte)

    // Charger l'exemple
    const btnExemple = screen.getByRole('button', { name: /Charger un exemple/i })
    await userEvent.click(btnExemple)

    // Cliquer sur le bouton d'analyse
    const btnLancer = screen.getByRole('button', { name: /Lancer l’audit documentaire/i })
    await userEvent.click(btnLancer)

    await waitFor(() => {
      expect(ragApi.analyserDocument).toHaveBeenCalledWith(
        expect.objectContaining({
          transaction: 'location',
          langue: 'fr',
        }),
      )
    })

    // Vérifier l'affichage du rapport
    const rapportEl = await screen.findByTestId('rapport-analyse')
    expect(rapportEl).toBeInTheDocument()
    expect(screen.getByText(/Saut de numérotation : page 2 manquante/i)).toBeInTheDocument()
    expect(screen.getByText(/08765432, 11223344/i)).toBeInTheDocument()
    expect(screen.getAllByText(/850 DT/i).length).toBeGreaterThanOrEqual(1)

    // Vérifier la callback vers le parent
    expect(callbackChecklist).toHaveBeenCalledWith(
      ['cin_proprietaire', 'cin_locataire', 'loyer_et_caution'],
      'location',
    )
  })
})
