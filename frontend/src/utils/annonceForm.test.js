import { describe, expect, it } from 'vitest'
import { STUDIO } from '../test/donnees'
import { VALEURS_VIDES, champsModifies, validerAnnonce, versApi, versFormulaire } from './annonceForm'

const VALIDE = { ...versFormulaire(STUDIO) }

describe('validerAnnonce', () => {
  it("n'a aucune erreur pour une annonce valide", () => {
    expect(validerAnnonce(VALIDE)).toEqual({})
  })

  it('signale les champs obligatoires, sauf latitude et longitude', () => {
    const erreurs = validerAnnonce(VALEURS_VIDES)
    expect(Object.keys(erreurs).sort()).toEqual(
      ['adresse', 'description', 'nb_pieces', 'prix', 'surface', 'titre', 'transaction', 'type_bien', 'ville'].sort(),
    )
    expect(erreurs.titre).toEqual(['Champ obligatoire.'])
  })

  it('applique les mêmes bornes que le backend', () => {
    expect(validerAnnonce({ ...VALIDE, titre: 'Abcd' }).titre).toEqual(['Doit contenir entre 5 et 150 caractères.'])
    expect(validerAnnonce({ ...VALIDE, titre: 'x'.repeat(151) }).titre).toBeDefined()
    expect(validerAnnonce({ ...VALIDE, titre: 'x'.repeat(150) }).titre).toBeUndefined()
    expect(validerAnnonce({ ...VALIDE, prix: '0' }).prix).toEqual(['Doit être supérieur à 0.'])
    expect(validerAnnonce({ ...VALIDE, surface: '-1' }).surface).toEqual(['Doit être supérieur à 0.'])
    expect(validerAnnonce({ ...VALIDE, nb_pieces: '0' }).nb_pieces).toBeUndefined()
    expect(validerAnnonce({ ...VALIDE, nb_pieces: '2.5' }).nb_pieces).toEqual(['Doit être un nombre entier.'])
    expect(validerAnnonce({ ...VALIDE, latitude: '-90' }).latitude).toBeUndefined()
    expect(validerAnnonce({ ...VALIDE, latitude: '90.1' }).latitude).toEqual(['Doit être compris entre -90 et 90.'])
    expect(validerAnnonce({ ...VALIDE, longitude: '180' }).longitude).toBeUndefined()
    expect(validerAnnonce({ ...VALIDE, longitude: 'abc' }).longitude).toEqual(['Valeur invalide.'])
  })
})

describe('versApi et champsModifies', () => {
  it('convertit les saisies en types attendus par l\'API', () => {
    const corps = versApi({ ...VALIDE, prix: '1200.5', latitude: '36.8', longitude: '', caracteristiques: ['piscine', 'balcon'] })
    expect(corps).toMatchObject({ prix: 1200.5, nb_pieces: 1, latitude: 36.8, longitude: null, caracteristiques: ['balcon', 'piscine'] })
  })

  it('ne garde que les champs modifiés', () => {
    const avant = versApi(versFormulaire(STUDIO))
    expect(champsModifies(avant, versApi(VALIDE))).toEqual({})
    expect(champsModifies(avant, versApi({ ...VALIDE, ville: 'Ariana', latitude: '36.86' }))).toEqual({
      ville: 'Ariana',
      latitude: 36.86,
    })
  })
})
