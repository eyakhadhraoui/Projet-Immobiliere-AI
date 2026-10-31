import { vi } from 'vitest'

/**
 * Fabrique du module api/annonces simulé, à utiliser dans vi.mock :
 *   vi.mock('../api/annonces', async (importOriginal) =>
 *     (await import('../test/apiSimulee')).simulerApi(await importOriginal()))
 * Toutes les fonctions de route sont des vi.fn() (aucun appel réseau possible) ;
 * seules les fonctions pures lireErreur et nettoyerFiltres gardent leur vrai comportement.
 */
export function simulerApi(reel) {
  return {
    lireErreur: reel.lireErreur,
    nettoyerFiltres: reel.nettoyerFiltres,
    listerAnnonces: vi.fn(),
    listerToutesLesAnnonces: vi.fn(),
    obtenirAnnonce: vi.fn(),
    creerAnnonce: vi.fn(),
    modifierAnnonce: vi.fn(),
    supprimerAnnonce: vi.fn(),
    changerStatut: vi.fn(),
    obtenirFiabiliteAnnonce: vi.fn(),
    demanderRevueFiabilite: vi.fn(),
    ajouterPhotos: vi.fn(),
    supprimerPhoto: vi.fn(),
    reordonnerPhotos: vi.fn(),
  }
}

/**
 * Fabrique du module api/historique simulé :
 *   vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
 */
export function simulerApiHistorique() {
  return {
    obtenirHistoriqueAnnonce: vi.fn(),
    listerHistorique: vi.fn(),
    obtenirStatistiques: vi.fn(),
  }
}

/**
 * Fabrique du module api/auth simulé :
 *   vi.mock('../api/auth', async () => (await import('../test/apiSimulee')).simulerApiAuth())
 */
export function simulerApiAuth() {
  return {
    inscription: vi.fn(),
    connexion: vi.fn(),
    verifierConnexion: vi.fn(),
    retourConnexion: vi.fn(),
    obtenirAlerteConnexion: vi.fn(),
    obtenirHistoriqueConnexions: vi.fn().mockResolvedValue([]),
    deconnexion: vi.fn(),
    obtenirSession: vi.fn(),
    modifierProfil: vi.fn(),
    changerMotDePasse: vi.fn(),
    envoyerPhotoProfil: vi.fn(),
    retirerPhotoProfil: vi.fn(),
    supprimerCompte: vi.fn(),
  }
}

/** Erreur axios simulée avec une réponse HTTP. */
export function erreurHttp(status, data) {
  return { isAxiosError: true, response: { status, data } }
}

/** Erreur axios simulée sans réponse (serveur injoignable). */
export function erreurReseau() {
  return { isAxiosError: true, message: 'Network Error', response: undefined }
}

/** Faux fichier image de la taille voulue (en octets). */
export function fichierImage(nom, taille = 1024, type = 'image/jpeg') {
  const fichier = new File(['x'], nom, { type })
  Object.defineProperty(fichier, 'size', { value: taille })
  return fichier
}
