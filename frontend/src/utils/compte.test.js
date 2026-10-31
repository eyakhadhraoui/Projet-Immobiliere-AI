import { describe, expect, it } from 'vitest'
import { PROPRIETAIRE_CONNECTE } from '../test/donnees'
import { cheminRetourSur, initiales, modificationsProfil, urlConnexion } from './compte'
import { evaluerMotDePasse } from './motDePasse'

describe('Compte', () => {
  it('accepte seulement un retour vers une page du site', () => {
    expect(cheminRetourSur('/espace/annonces?page=2')).toBe('/espace/annonces?page=2')
    expect(cheminRetourSur('//site-malveillant.example')).toBeNull()
    expect(cheminRetourSur('https://site-malveillant.example')).toBeNull()
    expect(cheminRetourSur('/\\site-malveillant.example')).toBeNull()
    expect(cheminRetourSur(null)).toBeNull()
  })

  it("construit l'adresse de connexion avec retour lisible", () => {
    expect(urlConnexion('/espace')).toBe('/connexion?retour=/espace')
    expect(urlConnexion('/espace/historique?action=modification')).toBe(
      '/connexion?retour=/espace/historique%3Faction%3Dmodification',
    )
  })

  it("calcule les initiales de l'avatar", () => {
    expect(initiales({ prenom: 'loujain', nom: 'rouached' })).toBe('LR')
    expect(initiales({ prenom: 'Sami' })).toBe('S')
    expect(initiales(null)).toBe('?')
  })

  it('ne garde que les champs modifiés ; un champ vidé devient null ; la CIN seulement si saisie', () => {
    const valeurs = { prenom: 'Loujain', nom: 'Rouached', email: 'loujain@example.com', telephone: '',
      date_naissance: '', ville: 'Tunis', adresse: '', cin_numero: '' }
    expect(modificationsProfil(PROPRIETAIRE_CONNECTE, valeurs)).toEqual({ telephone: null })
    expect(modificationsProfil(PROPRIETAIRE_CONNECTE, { ...valeurs, telephone: '+216 20 123 456', cin_numero: '87654321' }))
      .toEqual({ cin_numero: '87654321' })
  })
})

describe('Force du mot de passe', () => {
  it.each([
    ['', 'vide', false],
    ['abc', 'faible', false],
    ['abcdefgh', 'faible', false], // pas de chiffre : refusé par l'API
    ['maison2026', 'moyen', true],
    ['Maison-Bleue-2026', 'fort', true],
  ])('« %s » → %s', (motDePasse, niveau, valide) => {
    expect(evaluerMotDePasse(motDePasse)).toMatchObject({ niveau, valide })
  })
})
