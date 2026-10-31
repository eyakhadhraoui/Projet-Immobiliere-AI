import { CARACTERISTIQUES } from './annonceForm'
import {
  LIBELLES_STATUT,
  LIBELLES_TRANSACTION,
  LIBELLES_TYPE_BIEN,
  formaterDateHeure,
  formaterNombre,
  formaterPrix,
} from './format'

/** Libellé court affiché après le titre de l'annonce (ex. « Modifiée »). */
export const LIBELLES_ACTIONS = {
  creation: 'Créée',
  modification: 'Modifiée',
  changement_statut: 'Statut modifié',
  ajout_photos: 'Photos ajoutées',
  suppression_photo: 'Photo supprimée',
  reordonnancement_photos: 'Photos réordonnées',
  suppression: 'Supprimée',
}

/** Nom de l'action, pour le filtre de la page historique. */
export const NOMS_ACTIONS = {
  creation: 'Création',
  modification: 'Modification',
  changement_statut: 'Changement de statut',
  ajout_photos: 'Ajout de photos',
  suppression_photo: 'Suppression de photo',
  reordonnancement_photos: 'Réordonnancement des photos',
  suppression: 'Suppression',
}

const VIDE = '—'
const texte = (valeur) => (valeur === null || valeur === undefined || valeur === '' ? VIDE : String(valeur))
const nombre = (valeur) => (typeof valeur === 'number' ? formaterNombre(valeur) : texte(valeur))
const libelle = (libelles, valeur) => libelles[valeur] ?? texte(valeur)
const ouiNon = (valeur) => (valeur ? 'Oui' : 'Non')
const pluriel = (n, singulier, plurielMot) => `${n} ${n > 1 ? plurielMot : singulier}`

/** Description d'un champ modifié : « Prix 900 → 950 TND ». */
const DESCRIPTIONS_CHAMPS = {
  titre: ({ avant, apres }) => `Titre « ${texte(avant)} » → « ${texte(apres)} »`,
  description: () => 'Description modifiée',
  type_bien: ({ avant, apres }) => `Type ${libelle(LIBELLES_TYPE_BIEN, avant)} → ${libelle(LIBELLES_TYPE_BIEN, apres)}`,
  transaction: ({ avant, apres }) =>
    `Transaction ${libelle(LIBELLES_TRANSACTION, avant)} → ${libelle(LIBELLES_TRANSACTION, apres)}`,
  prix: ({ avant, apres }) => `Prix ${nombre(avant)} → ${nombre(apres)} TND`,
  surface: ({ avant, apres }) => `Surface ${nombre(avant)} → ${nombre(apres)} m²`,
  nb_pieces: ({ avant, apres }) => `Pièces ${texte(avant)} → ${texte(apres)}`,
  meuble: ({ avant, apres }) => `Meublé ${ouiNon(avant)} → ${ouiNon(apres)}`,
  adresse: ({ avant, apres }) => `Adresse « ${texte(avant)} » → « ${texte(apres)} »`,
  ville: ({ avant, apres }) => `Ville ${texte(avant)} → ${texte(apres)}`,
  latitude: ({ avant, apres }) => `Latitude ${texte(avant)} → ${texte(apres)}`,
  longitude: ({ avant, apres }) => `Longitude ${texte(avant)} → ${texte(apres)}`,
  caracteristiques: ({ avant = [], apres = [] }) => {
    const nom = (c) => CARACTERISTIQUES[c] ?? c
    const ajouts = apres.filter((c) => !avant.includes(c)).map((c) => `+ ${nom(c)}`)
    const retraits = avant.filter((c) => !apres.includes(c)).map((c) => `− ${nom(c)}`)
    return `Caractéristiques : ${[...ajouts, ...retraits].join(', ') || 'ordre modifié'}`
  },
}

/** Description des détails, selon le type d'action. */
const DESCRIPTIONS_ACTIONS = {
  creation: (d) =>
    [libelle(LIBELLES_TYPE_BIEN, d.type_bien), libelle(LIBELLES_TRANSACTION, d.transaction),
      typeof d.prix === 'number' ? formaterPrix(d.prix, d.transaction) : null, d.ville]
      .filter((partie) => partie && partie !== VIDE)
      .join(' · '),
  modification: (d) =>
    Object.entries(d)
      .map(([champ, valeurs]) =>
        (DESCRIPTIONS_CHAMPS[champ] ?? (({ avant, apres }) => `${champ} ${texte(avant)} → ${texte(apres)}`))(valeurs),
      )
      .join(' ; '),
  changement_statut: (d) => `${libelle(LIBELLES_STATUT, d.avant)} → ${libelle(LIBELLES_STATUT, d.apres)}`,
  ajout_photos: (d) => `${pluriel(d.nombre ?? 0, 'photo ajoutée', 'photos ajoutées')}`,
  suppression_photo: (d) => (d.position ? `Photo n° ${d.position} supprimée` : 'Photo supprimée'),
  reordonnancement_photos: () => 'Nouvel ordre des photos',
  suppression: (d) =>
    [d.statut ? `Statut : ${libelle(LIBELLES_STATUT, d.statut)}` : null,
      d.nb_photos ? pluriel(d.nb_photos, 'photo supprimée', 'photos supprimées') : null]
      .filter(Boolean)
      .join(' ; '),
}

/**
 * Décrit les détails d'une entrée d'historique en français.
 *
 * @param {{ action: string, details: object }} entree Entrée renvoyée par l'API.
 * @returns {string} Ex. "Prix 900 → 950 TND ; Meublé Non → Oui" (chaîne vide si rien à dire).
 */
export function decrireDetails(entree) {
  const decrire = DESCRIPTIONS_ACTIONS[entree.action]
  return decrire ? decrire(entree.details ?? {}) : ''
}

/**
 * Résumé d'une entrée sur une ligne.
 *
 * @param {object} entree Entrée renvoyée par l'API.
 * @returns {string} Ex. "Maison de vacances Bizerte — Modifiée : Prix 900 → 950 TND ; Meublé Non → Oui
 *   — 21/10/2026 à 12:50".
 */
export function resumerEntree(entree) {
  const details = decrireDetails(entree)
  const action = LIBELLES_ACTIONS[entree.action] ?? entree.action
  return `${entree.titre_annonce} — ${action}${details ? ` : ${details}` : ''} — ${formaterDateHeure(entree.created_at)}`
}
