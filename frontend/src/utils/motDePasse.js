/** Règles obligatoires : les mêmes que le backend (backend/app/schemas/utilisateur_schema.py). */
export const CRITERES_OBLIGATOIRES = [
  { id: 'longueur', libelle: 'Au moins 8 caractères', test: (mdp) => mdp.length >= 8 },
  { id: 'lettre', libelle: 'Au moins une lettre', test: (mdp) => /\p{L}/u.test(mdp) },
  { id: 'chiffre', libelle: 'Au moins un chiffre', test: (mdp) => /\d/.test(mdp) },
]

/** Critères conseillés : ils rendent le mot de passe « fort », sans être exigés. */
export const CRITERES_CONSEILLES = [
  { id: 'longueur12', libelle: '12 caractères ou plus', test: (mdp) => mdp.length >= 12 },
  { id: 'casse', libelle: 'Majuscules et minuscules', test: (mdp) => /\p{Lu}/u.test(mdp) && /\p{Ll}/u.test(mdp) },
  { id: 'special', libelle: 'Un caractère spécial (!, ?, @…)', test: (mdp) => /[^\p{L}\d]/u.test(mdp) },
]

export const LIBELLES_NIVEAU = { vide: '', faible: 'Faible', moyen: 'Moyen', fort: 'Fort' }

/**
 * Évalue un mot de passe pour l'indicateur de force.
 *
 * @param {string} motDePasse Mot de passe saisi.
 * @returns {{
 *   niveau: 'vide' | 'faible' | 'moyen' | 'fort',
 *   valide: boolean,
 *   criteres: { id: string, libelle: string, ok: boolean, obligatoire: boolean }[],
 * }} niveau « faible » tant qu'une règle obligatoire manque ; « fort » avec au moins 2 critères conseillés.
 */
export function evaluerMotDePasse(motDePasse = '') {
  const criteres = [
    ...CRITERES_OBLIGATOIRES.map((c) => ({ id: c.id, libelle: c.libelle, ok: c.test(motDePasse), obligatoire: true })),
    ...CRITERES_CONSEILLES.map((c) => ({ id: c.id, libelle: c.libelle, ok: c.test(motDePasse), obligatoire: false })),
  ]
  const valide = criteres.filter((c) => c.obligatoire).every((c) => c.ok)
  const bonus = criteres.filter((c) => !c.obligatoire && c.ok).length
  let niveau = 'faible'
  if (motDePasse === '') niveau = 'vide'
  else if (valide) niveau = bonus >= 2 ? 'fort' : 'moyen'
  return { niveau, valide, criteres }
}

/**
 * Message d'erreur du mot de passe (mêmes textes que l'API), ou null s'il est valide.
 *
 * @param {string} motDePasse Mot de passe saisi.
 * @returns {string[] | null} Messages.
 */
export function erreursMotDePasse(motDePasse = '') {
  if (motDePasse === '') return ['Champ obligatoire.']
  const messages = []
  if (motDePasse.length < 8) messages.push('Doit contenir au moins 8 caractères.')
  if (motDePasse.length > 128) messages.push('Doit contenir au plus 128 caractères.')
  if (!/\p{L}/u.test(motDePasse)) messages.push('Doit contenir au moins une lettre.')
  if (!/\d/.test(motDePasse)) messages.push('Doit contenir au moins un chiffre.')
  return messages.length > 0 ? messages : null
}
