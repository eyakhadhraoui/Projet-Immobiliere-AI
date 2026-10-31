import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import RapportInferenceLitigePage from './RapportInferenceLitigePage'

describe('RapportInferenceLitigePage', () => {
  it('traduit et signale comme captures fournies les résultats enregistrés', () => {
    render(<MemoryRouter><RapportInferenceLitigePage /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: 'Résultats enregistrés du modèle local' })).toBeInTheDocument()
    expect(screen.getByText('2 / 4 contrôles illustratifs réussis')).toBeInTheDocument()
    expect(screen.getByText(/ne sont pas produits par le modèle actuellement installé/i)).toBeInTheDocument()
    expect(screen.getByText('700 EUR')).toBeInTheDocument()
    expect(screen.getAllByText(/2026-03-03/).length).toBeGreaterThan(0)
  })
})
