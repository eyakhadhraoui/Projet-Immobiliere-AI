/** Compte propriétaire connecté (réponse de GET /api/auth/moi). */
export const PROPRIETAIRE_CONNECTE = {
  id: 1,
  nom: 'Rouached',
  prenom: 'Loujain',
  email: 'loujain@example.com',
  telephone: '+216 20 123 456',
  role: 'proprietaire',
  date_naissance: null,
  ville: 'Tunis',
  adresse: null,
  photo_profil: null,
  cin_numero: '******78',
  cin_verifiee: false,
  visage_verifie: false,
  derniere_connexion: '2026-10-23T14:00:00+00:00',
  created_at: '2026-10-23T14:10:00+00:00',
  updated_at: '2026-10-23T14:10:00+00:00',
}

/** Compte client connecté. */
export const CLIENT_CONNECTE = { ...PROPRIETAIRE_CONNECTE, id: 2, prenom: 'Ines', nom: 'Ben Ali', email: 'ines@example.com', role: 'client', cin_numero: null }

/** Entrée d'historique de l'exemple du prompt FRONT-004 (format de GET /api/historique). */
export const MODIFICATION_BIZERTE = {
  id: 12,
  annonce_id: 3,
  titre_annonce: 'Maison de vacances Bizerte',
  action: 'modification',
  details: { prix: { avant: 900, apres: 950 }, meuble: { avant: false, apres: true } },
  owner_id: 1,
  created_at: '2026-10-21T12:50:31+00:00',
}

/** Une entrée de chaque type d'action (annonce 7, puis suppression de l'annonce 5). */
export const HISTORIQUE = [
  MODIFICATION_BIZERTE,
  {
    id: 11, annonce_id: 7, titre_annonce: 'Studio centre Tunis', action: 'changement_statut',
    details: { avant: 'brouillon', apres: 'publiee' }, owner_id: 1, created_at: '2026-10-21T09:15:00+00:00',
  },
  {
    id: 10, annonce_id: 5, titre_annonce: 'Villa vendue', action: 'suppression',
    details: { statut: 'vendue', nb_photos: 2 }, owner_id: 1, created_at: '2026-10-20T17:00:00+00:00',
  },
  {
    id: 9, annonce_id: 7, titre_annonce: 'Studio centre Tunis', action: 'ajout_photos',
    details: { nombre: 3, photo_ids: [11, 12, 13] }, owner_id: 1, created_at: '2026-10-20T10:00:00+00:00',
  },
  {
    id: 8, annonce_id: 7, titre_annonce: 'Studio centre Tunis', action: 'creation',
    details: { statut: 'brouillon', type_bien: 'studio', transaction: 'location', prix: 600, ville: 'Tunis' },
    owner_id: 1, created_at: '2026-10-20T09:00:00+00:00',
  },
]

/** Annonce type renvoyée par l'API simulée (mêmes champs que Annonce.to_dict()). */
export const STUDIO = {
  id: 7,
  titre: 'Studio centre Tunis',
  description: 'Proche du métro.\nRefait à neuf.',
  type_bien: 'studio',
  transaction: 'location',
  prix: 600,
  surface: 35,
  nb_pieces: 1,
  meuble: false,
  adresse: 'Avenue Habib Bourguiba',
  ville: 'Tunis',
  latitude: null,
  longitude: null,
  caracteristiques: ['internet'],
  statut: 'brouillon',
  owner_id: 1,
  created_at: '2026-10-20T09:00:00+00:00',
  updated_at: '2026-10-21T09:00:00+00:00',
  photos: [
    { id: 11, annonce_id: 7, ordre: 1, url: '/uploads/a.jpg', type_piece: null },
    { id: 12, annonce_id: 7, ordre: 2, url: '/uploads/b.jpg', type_piece: null },
    { id: 13, annonce_id: 7, ordre: 3, url: '/uploads/c.jpg', type_piece: null },
  ],
}
