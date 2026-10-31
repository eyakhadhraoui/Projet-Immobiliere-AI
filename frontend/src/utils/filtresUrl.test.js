import { describe, expect, it } from 'vitest'
import { aDesFiltres, construireParams, lireFiltres, FILTRES_VIDES } from './filtresUrl'

describe('tri du catalogue', () => {
  it('garde le tri chronologique comme valeur par défaut et ne le compte pas comme filtre', () => {
    expect(lireFiltres(new URLSearchParams()).tri).toBe('chronologique')
    expect(aDesFiltres(FILTRES_VIDES)).toBe(false)
    expect(construireParams(FILTRES_VIDES)).toEqual({})
  })

  it('synchronise le classement de compatibilité avec l’URL', () => {
    const params = construireParams({ ...FILTRES_VIDES, ville: 'Tunis', tri: 'pertinence' })
    expect(params).toEqual({ ville: 'Tunis', tri: 'pertinence' })
    expect(lireFiltres(new URLSearchParams(params))).toMatchObject({ ville: 'Tunis', tri: 'pertinence' })
    expect(aDesFiltres({ ...FILTRES_VIDES, tri: 'pertinence' })).toBe(false)
  })
})
