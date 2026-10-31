import { describe, expect, it } from 'vitest'
import { ESPACE_INSECABLE, formaterPieces, formaterPrix, formaterSurface } from './format'

/** Écrit l'attendu avec des espaces normales, comparé avec des espaces insécables. */
const insecable = (texte) => texte.replaceAll(' ', ESPACE_INSECABLE)

describe('formatage', () => {
  it('utilise le caractère U+00A0', () => {
    expect(ESPACE_INSECABLE.charCodeAt(0)).toBe(0xa0)
  })

  it('formate un prix de vente en dinars', () => {
    expect(formaterPrix(250000, 'vente')).toBe(insecable('250 000 TND'))
  })

  it('ajoute /mois pour une location', () => {
    expect(formaterPrix(1200, 'location')).toBe(insecable('1 200 TND/mois'))
  })

  it('garde les décimales utiles', () => {
    expect(formaterPrix(950.5, 'location')).toBe(insecable('950,5 TND/mois'))
  })

  it('formate la surface et le nombre de pièces', () => {
    expect(formaterSurface(85)).toBe(insecable('85 m²'))
    expect(formaterPieces(1)).toBe(insecable('1 pièce'))
    expect(formaterPieces(3)).toBe(insecable('3 pièces'))
  })
})
