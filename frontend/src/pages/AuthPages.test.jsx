import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { connexion, deconnexion, inscription, retourConnexion, verifierConnexion } from '../api/auth'
import { listerAnnonces } from '../api/annonces'
import { obtenirStatistiques } from '../api/historique'
import { afficherApp } from '../test/afficherApp'
import { erreurHttp } from '../test/apiSimulee'
import { CLIENT_CONNECTE, PROPRIETAIRE_CONNECTE } from '../test/donnees'
import { motDePasseAleatoire } from '../test/outils'

vi.mock('../api/auth', async () => (await import('../test/apiSimulee')).simulerApiAuth())
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null })
const MOT_DE_PASSE = motDePasseAleatoire()

const STATISTIQUES = {
  total: 0,
  par_statut: { brouillon: 0, en_attente: 0, publiee: 0, louee: 0, vendue: 0 },
  par_type: { appartement: 0, maison: 0, studio: 0, villa: 0, residence: 0 },
  prix_moyen: { vente: null, location: null },
  dernieres_actions: [],
}

beforeEach(() => {
  vi.resetAllMocks()
  obtenirStatistiques.mockResolvedValue(STATISTIQUES)
  listerAnnonces.mockResolvedValue({ items: [], page: 1, per_page: 6, total: 0 })
})

describe('Routes protégées', () => {
  it('redirige un visiteur de /espace vers /connexion?retour=/espace, puis le renvoie sur /espace', async () => {
    const user = utilisateur()
    connexion.mockResolvedValue(PROPRIETAIRE_CONNECTE)
    afficherApp('/espace', { utilisateur: null })

    expect(screen.getByTestId('url')).toHaveTextContent(/^\/connexion\?retour=\/espace$/)
    await user.type(screen.getByLabelText('Email'), 'loujain@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Tableau de bord' })).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/espace$/)
    expect(connexion).toHaveBeenCalledWith('loujain@example.com', MOT_DE_PASSE)
  })

  it('affiche « Espace réservé aux propriétaires » à un client connecté', () => {
    afficherApp('/espace/annonces', { utilisateur: CLIENT_CONNECTE })

    expect(screen.getByRole('heading', { level: 1, name: 'Espace réservé aux propriétaires' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: "← Retour à l'accueil" })).toHaveAttribute('href', '/')
    expect(obtenirStatistiques).not.toHaveBeenCalled()
  })

  it('protège la page profil', () => {
    afficherApp('/profil', { utilisateur: null })
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/connexion\?retour=\/profil$/)
  })

  it("ignore une adresse de retour vers un autre site", async () => {
    const user = utilisateur()
    connexion.mockResolvedValue(CLIENT_CONNECTE)
    afficherApp('/connexion?retour=//site-malveillant.example', { utilisateur: null })

    await user.type(screen.getByLabelText('Email'), 'ines@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Trouvez le bien qui vous correspond' })).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/$/)
  })
})

describe('Connexion', () => {
  it('demande le code e-mail avant de terminer une connexion à risque élevé', async () => {
    const user = utilisateur()
    connexion.mockResolvedValue({ verification_requise: true, jeton_verification: 'defi-opaque', message: 'Code envoyé par e-mail.' })
    verifierConnexion.mockResolvedValue(CLIENT_CONNECTE)
    afficherApp('/connexion', { utilisateur: null })

    await user.type(screen.getByLabelText('Email'), 'ines@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByLabelText('Code reçu par e-mail')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Code reçu par e-mail'), '123456')
    await user.click(screen.getByRole('button', { name: 'Vérifier et se connecter' }))

    expect(verifierConnexion).toHaveBeenCalledWith('defi-opaque', '123456')
    expect(await screen.findByRole('heading', { level: 1, name: 'Trouvez le bien qui vous correspond' })).toBeInTheDocument()
  })

  it('affiche et enregistre la confirmation d’une connexion inhabituelle', async () => {
    const user = utilisateur()
    connexion.mockResolvedValue({ ...CLIENT_CONNECTE, alerte_connexion: { evenement_id: 17, message: 'Connexion détectée.' } })
    retourConnexion.mockResolvedValue({ message: 'Connexion confirmée.' })
    afficherApp('/connexion', { utilisateur: null })

    await user.type(screen.getByLabelText('Email'), 'ines@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Connexion détectée.')
    await user.click(within(alerte).getByRole('button', { name: 'C’était moi' }))

    expect(retourConnexion).toHaveBeenCalledWith(17, 'confirmee')
  })

  it('affiche le message de l’API sans révéler si l’email existe, et vide le mot de passe', async () => {
    const user = utilisateur()
    connexion.mockRejectedValue(
      erreurHttp(401, { error: 'identifiants_invalides', message: 'Email ou mot de passe incorrect.' }),
    )
    afficherApp('/connexion', { utilisateur: null })

    await user.type(screen.getByLabelText('Email'), 'inconnu@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Email ou mot de passe incorrect.')
    expect(screen.getByLabelText('Mot de passe')).toHaveValue('')
    expect(screen.getByTestId('url')).toHaveTextContent('/connexion')
  })

  it('affiche le blocage temporaire (429)', async () => {
    const user = utilisateur()
    connexion.mockRejectedValue(
      erreurHttp(429, { error: 'trop_de_tentatives', message: 'Trop de tentatives de connexion. Réessayez dans 15 minutes.' }),
    )
    afficherApp('/connexion', { utilisateur: null })

    await user.type(screen.getByLabelText('Email'), 'loujain@example.com')
    await user.type(screen.getByLabelText('Mot de passe'), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Réessayez dans 15 minutes.')
  })

  it('exige les deux champs et permet d’afficher le mot de passe', async () => {
    const user = utilisateur()
    afficherApp('/connexion', { utilisateur: null })

    await user.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(document.getElementById('erreur-email')).toHaveTextContent('Champ obligatoire.')
    expect(document.getElementById('erreur-mot_de_passe')).toHaveTextContent('Champ obligatoire.')
    expect(connexion).not.toHaveBeenCalled()

    const champ = screen.getByLabelText('Mot de passe')
    expect(champ).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Afficher le mot de passe' }))
    expect(champ).toHaveAttribute('type', 'text')
  })
})

describe('Inscription', () => {
  async function remplir(user, motDePasse = MOT_DE_PASSE) {
    await user.click(screen.getByLabelText(/Je propose des biens/))
    await user.type(screen.getByLabelText('Prénom *'), 'Loujain')
    await user.type(screen.getByLabelText('Nom *'), 'Rouached')
    await user.type(screen.getByLabelText('Email *'), 'loujain@example.com')
    await user.type(screen.getByLabelText('Ville'), 'Tunis')
    await user.type(screen.getByLabelText('Mot de passe *'), motDePasse)
    await user.type(screen.getByLabelText('Confirmer le mot de passe *'), motDePasse)
  }

  it("crée un compte propriétaire et ouvre l'espace avec un message de bienvenue", async () => {
    const user = utilisateur()
    inscription.mockResolvedValue(PROPRIETAIRE_CONNECTE)
    afficherApp('/inscription', { utilisateur: null })

    await remplir(user)
    await user.click(screen.getByRole('button', { name: 'Créer mon compte' }))

    expect(await screen.findByText('Bienvenue Loujain ! Votre compte est créé.')).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/espace$/)
    expect(inscription).toHaveBeenCalledWith({
      prenom: 'Loujain', nom: 'Rouached', email: 'loujain@example.com', ville: 'Tunis', role: 'proprietaire',
      mot_de_passe: MOT_DE_PASSE,
    })
  })

  it('indique la force du mot de passe', async () => {
    const user = utilisateur()
    afficherApp('/inscription', { utilisateur: null })
    const champ = screen.getByLabelText('Mot de passe *')

    expect(screen.getByText('Choisissez un mot de passe.')).toBeInTheDocument()
    await user.type(champ, 'abc')
    expect(screen.getByText('Force : Faible')).toBeInTheDocument()
    expect(screen.getByText(/Au moins 8 caractères/).closest('li')).toHaveTextContent('non respecté')
    await user.clear(champ)
    await user.type(champ, 'maison2026')
    expect(screen.getByText('Force : Moyen')).toBeInTheDocument()
    await user.clear(champ)
    await user.type(champ, 'Maison-Bleue-2026')
    expect(screen.getByText('Force : Fort')).toBeInTheDocument()
    expect(champ).toHaveAttribute('aria-describedby', 'force-mot-de-passe')
  })

  it('valide le formulaire avant envoi', async () => {
    const user = utilisateur()
    afficherApp('/inscription', { utilisateur: null })

    await user.type(screen.getByLabelText('Mot de passe *'), 'motdepasse')
    await user.type(screen.getByLabelText('Confirmer le mot de passe *'), 'autre')
    await user.click(screen.getByRole('button', { name: 'Créer mon compte' }))

    expect(document.getElementById('erreur-role')).toHaveTextContent('Choisissez un type de compte.')
    expect(document.getElementById('erreur-prenom')).toHaveTextContent('Champ obligatoire.')
    expect(document.getElementById('erreur-mot_de_passe')).toHaveTextContent('Doit contenir au moins un chiffre.')
    expect(document.getElementById('erreur-confirmation')).toHaveTextContent('Les deux mots de passe ne correspondent pas.')
    expect(inscription).not.toHaveBeenCalled()
  })

  it("affiche sous le champ email l'erreur 409 de l'API", async () => {
    const user = utilisateur()
    inscription.mockRejectedValue(erreurHttp(409, { error: 'conflit', message: 'Un compte existe déjà avec cet email.' }))
    afficherApp('/inscription', { utilisateur: null })

    await remplir(user)
    await user.click(screen.getByRole('button', { name: 'Créer mon compte' }))

    expect(await screen.findByText('Un compte existe déjà avec cet email.')).toHaveAttribute('id', 'erreur-email')
    expect(screen.getByLabelText('Email *')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('En-tête selon la session', () => {
  it('visiteur : boutons Connexion et Inscription', () => {
    afficherApp('/', { utilisateur: null })
    const entete = screen.getByRole('banner')
    expect(within(entete).getByRole('link', { name: 'Connexion' })).toHaveAttribute('href', '/connexion')
    expect(within(entete).getByRole('link', { name: 'Inscription' })).toHaveAttribute('href', '/inscription')
  })

  it('client : menu du compte sans « Mon espace » ni lien vers l’espace propriétaire', async () => {
    const user = utilisateur()
    afficherApp('/', { utilisateur: CLIENT_CONNECTE })

    expect(screen.queryByRole('link', { name: 'Espace propriétaire' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Ines — menu du compte/ }))
    expect(screen.getByRole('link', { name: 'Mon profil' })).toHaveAttribute('href', '/profil')
    expect(screen.queryByRole('link', { name: 'Mon espace' })).not.toBeInTheDocument()
  })

  it('propriétaire : menu avec « Mon espace », fermeture avec Échap, puis déconnexion', async () => {
    const user = utilisateur()
    deconnexion.mockResolvedValue()
    afficherApp('/', { utilisateur: PROPRIETAIRE_CONNECTE })
    const bouton = screen.getByRole('button', { name: /Loujain — menu du compte/ })

    await user.click(bouton)
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Mon espace' })).toHaveAttribute('href', '/espace')
    await user.keyboard('{Escape}')
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    expect(bouton).toHaveFocus()

    await user.click(bouton)
    await user.click(screen.getByRole('button', { name: 'Déconnexion' }))

    expect(deconnexion).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Vous êtes déconnecté.')).toBeInTheDocument()
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Connexion' })).toBeInTheDocument()
  })
})
