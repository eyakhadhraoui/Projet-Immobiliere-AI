/**
 * Mot de passe valide (lettres et chiffres, 13 caractères), généré à chaque exécution :
 * aucun mot de passe n'est écrit dans le code des tests (USER-002).
 */
export function motDePasseAleatoire() {
  return `Mdp${crypto.randomUUID().replaceAll('-', '').slice(0, 9)}7`
}
