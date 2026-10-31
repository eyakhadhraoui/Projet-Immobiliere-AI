import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ListeVilles from './ListeVilles'
import { listerVilles } from '../api/ia'
import { viderCacheVilles } from '../hooks/useVilles'

vi.mock('../api/ia', () => ({ listerVilles: vi.fn() }))

beforeEach(() => {
  vi.resetAllMocks()
  viderCacheVilles()
})

function Champ() {
  return (
    <>
      <label htmlFor="v">Ville</label>
      <input id="v" list="villes-test" />
      <ListeVilles id="villes-test" />
    </>
  )
}

describe('ListeVilles', () => {
  it('propose les villes connues du modèle dans une liste reliée au champ', async () => {
    listerVilles.mockResolvedValue([
      { nom: 'La Marsa', nb_annonces: 290 },
      { nom: 'Tozeur', nb_annonces: 1 },
    ])
    const { container } = render(<Champ />)
    await waitFor(() => expect(container.querySelectorAll('#villes-test option')).toHaveLength(2))
    const options = [...container.querySelectorAll('#villes-test option')]
    expect(options.map((o) => o.value)).toEqual(['La Marsa', 'Tozeur'])
    expect(options[1].getAttribute('label')).toBe('Tozeur (1 annonce de référence)')
    expect(screen.getByLabelText('Ville')).toHaveAttribute('list', 'villes-test')
  })

  it('une seule requête pour plusieurs champs, et saisie libre si l’API échoue', async () => {
    listerVilles.mockRejectedValue(new Error('réseau'))
    const user = userEvent.setup()
    const { container } = render(
      <>
        <Champ />
        <ListeVilles id="autre" />
      </>,
    )
    await waitFor(() => expect(listerVilles).toHaveBeenCalledTimes(1))
    expect(container.querySelectorAll('option')).toHaveLength(0)
    await user.type(screen.getByLabelText('Ville'), 'Kélibia')
    expect(screen.getByLabelText('Ville')).toHaveValue('Kélibia')
  })
})
