import { describe, expect, it } from 'vitest'
import { MODIFICATION_BIZERTE } from '../test/donnees'
import { decrireDetails, resumerEntree } from './historique'

const entree = (action, details) => ({ action, details, titre_annonce: 'T', created_at: '2026-10-21T12:50:31+00:00' })

describe("Description de l'historique", () => {
  it("reproduit l'exemple attendu (fuseau UTC dans les tests)", () => {
    expect(resumerEntree(MODIFICATION_BIZERTE)).toBe(
      'Maison de vacances Bizerte — Modifiée : Prix 900 → 950 TND ; Meublé Non → Oui — 21/10/2026 à 12:50',
    )
  })

  it('décrit chaque type de champ modifié', () => {
    const details = decrireDetails(
      entree('modification', {
        titre: { avant: 'Ancien titre', apres: 'Nouveau titre' },
        type_bien: { avant: 'studio', apres: 'appartement' },
        surface: { avant: 35, apres: 40 },
        nb_pieces: { avant: 1, apres: 2 },
        ville: { avant: 'Tunis', apres: 'Ariana' },
        latitude: { avant: null, apres: 36.86 },
        description: { avant: 'a', apres: 'b' },
        caracteristiques: { avant: ['internet', 'jardin'], apres: ['internet', 'parking'] },
      }),
    )
    expect(details).toBe(
      'Titre « Ancien titre » → « Nouveau titre » ; Type Studio → Appartement ; Surface 35 → 40 m² ; ' +
        'Pièces 1 → 2 ; Ville Tunis → Ariana ; Latitude — → 36.86 ; Description modifiée ; ' +
        'Caractéristiques : + Parking, − Jardin',
    )
  })

  it.each([
    ['changement_statut', { avant: 'brouillon', apres: 'publiee' }, 'Brouillon → Publiée'],
    ['ajout_photos', { nombre: 1, photo_ids: [4] }, '1 photo ajoutée'],
    ['ajout_photos', { nombre: 3, photo_ids: [4, 5, 6] }, '3 photos ajoutées'],
    ['suppression_photo', { photo_id: 4, position: 2 }, 'Photo n° 2 supprimée'],
    ['reordonnancement_photos', { avant: [1, 2], apres: [2, 1] }, 'Nouvel ordre des photos'],
    ['suppression', { statut: 'vendue', nb_photos: 2 }, 'Statut : Vendue ; 2 photos supprimées'],
    ['creation', { statut: 'brouillon', type_bien: 'villa', transaction: 'vente', prix: 450000, ville: 'Sousse' },
      'Villa · Vente · 450 000 TND · Sousse'],
  ])('décrit l\'action %s', (action, details, attendu) => {
    // Les montants utilisent des espaces insécables : on compare avec des espaces normales.
    expect(decrireDetails(entree(action, details)).replace(/\s/g, ' ')).toBe(attendu)
  })
})
