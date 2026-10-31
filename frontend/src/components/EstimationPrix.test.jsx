import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EstimationPrix from './EstimationPrix'
import { estimerPrix } from '../api/ia'

vi.mock('../api/ia', () => ({ estimerPrix: vi.fn() }))

const VALEURS = {
  type_bien: 'studio',
  transaction: 'location',
  ville: 'Tunis',
  surface: '35',
  nb_pieces: '1',
  meuble: true,
  caracteristiques: ['parking'],
}

const RESULTAT = {
  prix_estime: 750,
  fourchette: { min: 600, max: 900 },
  transaction: 'location',
  facteurs: [],
  modele: { nom: 'RandomForestRegressor', mape_test: 12.3, entraine_le: '2026-01-01' },
  avertissement: 'Estimation indicative de démonstration.',
}

beforeEach(() => vi.resetAllMocks())

describe('EstimationPrix', () => {
  it('affiche l’avertissement synthétique et demande une estimation avec les caractéristiques du formulaire', async () => {
    const user = userEvent.setup()
    estimerPrix.mockResolvedValue(RESULTAT)
    render(<EstimationPrix valeurs={VALEURS} onUtiliserPrix={vi.fn()} />)

    // Avant l'estimation, la provenance du modèle n'est pas encore connue (IA-ANNONCE-PPT-001).
    expect(screen.getByText(/provenance des données d’entraînement est précisée avec le résultat/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))

    expect(estimerPrix).toHaveBeenCalledWith({
      ...VALEURS,
      surface: 35,
      nb_pieces: 1,
      caracteristiques: ['parking'],
    })
    expect(await screen.findByText(/Prix estimé/)).toHaveTextContent('750')
    expect(screen.getByText(/Fourchette probable/)).toHaveTextContent('600')
    expect(screen.getByText(/non représentatives de la précision du marché réel/)).toBeInTheDocument()
    expect(screen.getByText(/données synthétiques de démonstration/)).toBeInTheDocument()
  })

  it('annonce un modèle entraîné sur des annonces réelles (IA-ANNONCE-PPT-001)', async () => {
    const user = userEvent.setup()
    estimerPrix.mockResolvedValue({ ...RESULTAT, modele: { ...RESULTAT.modele, source: 'annonces_reelles' } })
    render(<EstimationPrix valeurs={VALEURS} onUtiliserPrix={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))

    expect(await screen.findByText(/annonces immobilières réelles publiées en ligne/)).toBeInTheDocument()
    expect(screen.getByText(/repris des données de démonstration/)).toBeInTheDocument()
    expect(screen.queryByText(/données synthétiques/)).not.toBeInTheDocument()
  })

  it('envoie le nombre de salles de bain facultatif, et le refuse s’il est invalide', async () => {
    const user = userEvent.setup()
    estimerPrix.mockResolvedValue(RESULTAT)
    render(<EstimationPrix valeurs={VALEURS} onUtiliserPrix={vi.fn()} />)
    const champ = screen.getByLabelText('Salles de bain (facultatif)')

    await user.type(champ, '2.5')
    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    expect(screen.getByRole('alert')).toHaveTextContent('nombre entier entre 0 et 20')
    expect(estimerPrix).not.toHaveBeenCalled()

    await user.clear(champ)
    await user.type(champ, '2')
    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    expect(estimerPrix).toHaveBeenCalledWith(expect.objectContaining({ nb_sdb: 2 }))
  })

  it('affiche le niveau de confiance et ses raisons (IA-ANNONCE-001-ROBUSTE)', async () => {
    const user = userEvent.setup()
    estimerPrix.mockResolvedValue({
      ...RESULTAT,
      confiance: { niveau: 'élevée', raisons: ["Bien comparable aux annonces d'entraînement"] },
    })
    render(<EstimationPrix valeurs={VALEURS} onUtiliserPrix={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))

    expect(await screen.findByText(/Confiance :/)).toHaveTextContent('Confiance : élevée')
    expect(screen.getByText("Bien comparable aux annonces d'entraînement")).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('met l’avertissement en évidence, avant le prix, quand la confiance est faible', async () => {
    const user = userEvent.setup()
    estimerPrix.mockResolvedValue({
      ...RESULTAT,
      confiance: {
        niveau: 'faible',
        raisons: ['Ville « Tozeur » absente des données d’entraînement', 'Surface de 450 m² au-delà de la plage connue (25–430 m²)'],
      },
      avertissement: 'Estimation peu fiable pour ce bien : à utiliser avec prudence.',
    })
    render(<EstimationPrix valeurs={{ ...VALEURS, ville: 'Tozeur' }} onUtiliserPrix={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveClass('estimation__alerte')
    expect(alerte).toHaveTextContent('Confiance faible')
    expect(alerte).toHaveTextContent('Ville « Tozeur » absente des données d’entraînement')
    expect(alerte).toHaveTextContent('Surface de 450 m² au-delà de la plage connue (25–430 m²)')
    expect(alerte).toHaveTextContent('Estimation peu fiable pour ce bien : à utiliser avec prudence.')
    // L'alerte précède le prix estimé dans l'ordre de lecture.
    const prix = screen.getByText(/Prix estimé/)
    expect(alerte.compareDocumentPosition(prix) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // L'avertissement n'est pas répété hors de l'alerte.
    expect(screen.getAllByText(/Estimation peu fiable pour ce bien/)).toHaveLength(1)
  })

  it('affiche une erreur API sans perdre le formulaire', async () => {
    const user = userEvent.setup()
    estimerPrix.mockRejectedValue({ response: { status: 503, data: {} } })
    render(<EstimationPrix valeurs={VALEURS} onUtiliserPrix={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("le modèle n'a pas encore été entraîné")
  })

  it('reprend directement le prix si le champ est vide', async () => {
    const user = userEvent.setup()
    const onUtiliserPrix = vi.fn()
    estimerPrix.mockResolvedValue(RESULTAT)
    render(<EstimationPrix valeurs={VALEURS} prixActuel="" onUtiliserPrix={onUtiliserPrix} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    await screen.findByText(/Prix estimé/)
    await user.click(screen.getByRole('button', { name: 'Utiliser ce prix' }))

    expect(onUtiliserPrix).toHaveBeenCalledWith(750)
  })

  it('demande confirmation avant de remplacer un prix déjà saisi', async () => {
    const user = userEvent.setup()
    const onUtiliserPrix = vi.fn()
    estimerPrix.mockResolvedValue(RESULTAT)
    render(<EstimationPrix valeurs={VALEURS} prixActuel="620" onUtiliserPrix={onUtiliserPrix} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    await screen.findByText(/Prix estimé/)
    await user.click(screen.getByRole('button', { name: 'Utiliser ce prix' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent('620 TND')
    expect(onUtiliserPrix).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Garder le prix saisi' }))
    expect(onUtiliserPrix).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Utiliser ce prix' }))
    await user.click(screen.getByRole('button', { name: 'Remplacer le prix' }))
    expect(onUtiliserPrix).toHaveBeenCalledWith(750)
  })

  it('bloque la demande quand les caractéristiques obligatoires manquent', async () => {
    const user = userEvent.setup()
    render(<EstimationPrix valeurs={{ ...VALEURS, ville: '' }} onUtiliserPrix={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Estimer le prix' }))
    expect(screen.getByRole('alert')).toHaveTextContent('ville')
    expect(estimerPrix).not.toHaveBeenCalled()
  })
})
