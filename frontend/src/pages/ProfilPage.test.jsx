import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  changerMotDePasse,
  envoyerPhotoProfil,
  modifierProfil,
  obtenirSession,
  obtenirHistoriqueConnexions,
  retirerPhotoProfil,
  supprimerCompte,
} from '../api/auth'
import { listerAnnonces, obtenirAnnonce } from '../api/annonces'
import App from '../App'
import FournisseurAuth from '../contexts/FournisseurAuth'
import { afficherApp } from '../test/afficherApp'
import { erreurHttp, fichierImage } from '../test/apiSimulee'
import { CLIENT_CONNECTE, PROPRIETAIRE_CONNECTE, STUDIO } from '../test/donnees'
import { motDePasseAleatoire } from '../test/outils'

vi.mock('../api/auth', async () => (await import('../test/apiSimulee')).simulerApiAuth())
vi.mock('../api/historique', async () => (await import('../test/apiSimulee')).simulerApiHistorique())
vi.mock('../api/annonces', async (importOriginal) =>
  (await import('../test/apiSimulee')).simulerApi(await importOriginal()),
)

const utilisateur = () => userEvent.setup({ delay: null, applyAccept: false })
const MOT_DE_PASSE = motDePasseAleatoire()
const NOUVEAU = motDePasseAleatoire()

beforeEach(() => {
  vi.resetAllMocks()
  listerAnnonces.mockResolvedValue({ items: [], page: 1, per_page: 6, total: 0 })
  obtenirHistoriqueConnexions.mockResolvedValue([])
})

async function afficherProfil(compte = PROPRIETAIRE_CONNECTE) {
  afficherApp('/profil', { utilisateur: compte })
  return screen.findByRole('heading', { level: 1, name: `${compte.prenom} ${compte.nom}` })
}

describe('Mon profil : consultation et modification', () => {
  it('affiche l’historique privé des connexions', async () => {
    obtenirHistoriqueConnexions.mockResolvedValue([{
      id: 1, date: '2026-10-25T18:00:00+00:00', reussie: true, navigateur: 'Chrome',
      appareil: 'ordinateur', lieu: 'Réseau local', risque: 'suspect', retour: 'confirmee',
    }])
    await afficherProfil()
    const section = screen.getByRole('region', { name: 'Historique des connexions' })
    expect(section).toHaveTextContent('Connexion réussie')
    expect(section).toHaveTextContent('Chrome · ordinateur · Réseau local')
    expect(section).toHaveTextContent('Confirmée par vous')
  })

  it('affiche les informations, le rôle et les vérifications « bientôt disponibles »', async () => {
    await afficherProfil()

    expect(screen.getByText('Propriétaire', { selector: '.badge' })).toBeInTheDocument()
    expect(screen.getByLabelText('Prénom *')).toHaveValue('Loujain')
    expect(screen.getByLabelText('Email *')).toHaveValue('loujain@example.com')
    expect(screen.getByLabelText('Nouveau numéro de CIN')).toHaveValue('')
    expect(screen.getByText(/CIN enregistrée : \*{6}78/)).toBeInTheDocument()
    expect(screen.getByText('CIN : non vérifié', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Visage : non vérifié', { exact: false })).toBeInTheDocument()
    expect(screen.getByText(/La vérification automatique de la CIN et du visage arrive bientôt/)).toBeInTheDocument()
  })

  it("n'envoie que les champs modifiés et met à jour l'en-tête", async () => {
    const user = utilisateur()
    modifierProfil.mockResolvedValue({ ...PROPRIETAIRE_CONNECTE, prenom: 'Loujaine', ville: 'Sousse' })
    await afficherProfil()

    await user.clear(screen.getByLabelText('Prénom *'))
    await user.type(screen.getByLabelText('Prénom *'), 'Loujaine')
    await user.clear(screen.getByLabelText('Ville'))
    await user.type(screen.getByLabelText('Ville'), 'Sousse')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('Vos informations ont été enregistrées.')).toBeInTheDocument()
    expect(modifierProfil).toHaveBeenCalledWith({ prenom: 'Loujaine', ville: 'Sousse' })
    expect(screen.getByRole('button', { name: /Loujaine — menu du compte/ })).toBeInTheDocument()
  })

  it("n'appelle pas l'API sans modification et valide les champs", async () => {
    const user = utilisateur()
    await afficherProfil()

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(screen.getByText('Aucune modification à enregistrer.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Nouveau numéro de CIN'), '123')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(document.getElementById('erreur-cin_numero')).toHaveTextContent('La CIN doit contenir exactement 8 chiffres.')
    expect(modifierProfil).not.toHaveBeenCalled()
  })

  it('affiche sous le champ email un email déjà utilisé (409)', async () => {
    const user = utilisateur()
    modifierProfil.mockRejectedValue(erreurHttp(409, { error: 'conflit', message: 'Un compte existe déjà avec cet email.' }))
    await afficherProfil()

    await user.clear(screen.getByLabelText('Email *'))
    await user.type(screen.getByLabelText('Email *'), 'autre@example.com')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('Un compte existe déjà avec cet email.')).toHaveAttribute('id', 'erreur-email')
  })
})

describe('Mon profil : photo', () => {
  it("prévisualise la photo choisie avant de l'envoyer", async () => {
    const user = utilisateur()
    envoyerPhotoProfil.mockResolvedValue({ ...PROPRIETAIRE_CONNECTE, photo_profil: '/uploads/moi.jpg' })
    await afficherProfil()
    const photo = fichierImage('moi.jpg')

    await user.upload(screen.getByLabelText('Choisir une nouvelle photo'), photo)
    expect(screen.getByRole('img', { name: 'Aperçu : moi.jpg' })).toHaveAttribute('src', expect.stringMatching(/^blob:/))
    expect(envoyerPhotoProfil).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Enregistrer la photo' }))

    expect(await screen.findByText('Photo de profil mise à jour.')).toBeInTheDocument()
    expect(envoyerPhotoProfil).toHaveBeenCalledWith(photo)
    expect(screen.getByRole('img', { name: 'Votre photo de profil actuelle' })).toHaveAttribute('src', '/uploads/moi.jpg')
  })

  it('refuse un format non accepté sans appeler l’API, et retire la photo existante', async () => {
    const user = utilisateur()
    retirerPhotoProfil.mockResolvedValue({ ...PROPRIETAIRE_CONNECTE, photo_profil: null })
    await afficherProfil({ ...PROPRIETAIRE_CONNECTE, photo_profil: '/uploads/ancienne.jpg' })

    await user.upload(screen.getByLabelText('Choisir une nouvelle photo'), fichierImage('cv.pdf', 1024, 'application/pdf'))
    expect(screen.getByRole('alert')).toHaveTextContent('cv.pdf : format non accepté')
    expect(envoyerPhotoProfil).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Retirer la photo' }))
    expect(await screen.findByText('Photo de profil retirée.')).toBeInTheDocument()
  })
})

describe('Mon profil : mot de passe', () => {
  it('vérifie la confirmation, puis change le mot de passe', async () => {
    const user = utilisateur()
    changerMotDePasse.mockResolvedValue(PROPRIETAIRE_CONNECTE)
    await afficherProfil()

    await user.type(screen.getByLabelText('Mot de passe actuel'), MOT_DE_PASSE)
    await user.type(screen.getByLabelText('Nouveau mot de passe'), NOUVEAU)
    await user.type(screen.getByLabelText('Confirmer le nouveau mot de passe'), `${NOUVEAU}x`)
    await user.click(screen.getByRole('button', { name: 'Changer le mot de passe' }))
    expect(document.getElementById('erreur-confirmation')).toHaveTextContent('Les deux mots de passe ne correspondent pas.')
    expect(changerMotDePasse).not.toHaveBeenCalled()

    await user.clear(screen.getByLabelText('Confirmer le nouveau mot de passe'))
    await user.type(screen.getByLabelText('Confirmer le nouveau mot de passe'), NOUVEAU)
    await user.click(screen.getByRole('button', { name: 'Changer le mot de passe' }))

    expect(await screen.findByText('Mot de passe modifié. Vos autres sessions ont été fermées.')).toBeInTheDocument()
    expect(changerMotDePasse).toHaveBeenCalledWith(MOT_DE_PASSE, NOUVEAU)
    expect(screen.getByLabelText('Mot de passe actuel')).toHaveValue('')
  })

  it("affiche l'erreur de l'API sous l'ancien mot de passe", async () => {
    const user = utilisateur()
    changerMotDePasse.mockRejectedValue(
      erreurHttp(400, { error: 'validation', details: { ancien_mot_de_passe: ['Mot de passe incorrect.'] } }),
    )
    await afficherProfil()

    await user.type(screen.getByLabelText('Mot de passe actuel'), MOT_DE_PASSE)
    await user.type(screen.getByLabelText('Nouveau mot de passe'), NOUVEAU)
    await user.type(screen.getByLabelText('Confirmer le nouveau mot de passe'), NOUVEAU)
    await user.click(screen.getByRole('button', { name: 'Changer le mot de passe' }))

    expect(await screen.findByText('Mot de passe incorrect.')).toHaveAttribute('id', 'erreur-ancien')
  })
})

describe('Mon profil : suppression du compte', () => {
  it('demande le mot de passe, confirme en précisant que les annonces seront supprimées, puis déconnecte', async () => {
    const user = utilisateur()
    supprimerCompte.mockResolvedValue()
    await afficherProfil()

    await user.click(screen.getByRole('button', { name: 'Supprimer mon compte' }))
    expect(document.getElementById('erreur-mot_de_passe_suppression')).toHaveTextContent('Saisissez votre mot de passe')

    await user.type(screen.getByLabelText('Mot de passe', { selector: '#champ-mot_de_passe_suppression' }), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Supprimer mon compte' }))
    const fenetre = screen.getByRole('alertdialog', { name: 'Supprimer définitivement votre compte ?' })
    expect(fenetre).toHaveTextContent('toutes vos annonces, avec leurs photos, seront supprimés')
    expect(supprimerCompte).not.toHaveBeenCalled()

    await user.click(within(fenetre).getByRole('button', { name: 'Supprimer mon compte' }))

    expect(await screen.findByText('Votre compte a été supprimé.')).toBeInTheDocument()
    expect(supprimerCompte).toHaveBeenCalledWith(MOT_DE_PASSE)
    expect(screen.getByTestId('url')).toHaveTextContent(/^\/$/)
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Connexion' })).toBeInTheDocument()
  })

  it('ne parle pas d’annonces pour un client, et affiche un mot de passe incorrect', async () => {
    const user = utilisateur()
    supprimerCompte.mockRejectedValue(erreurHttp(400, { error: 'validation', details: { mot_de_passe: ['Mot de passe incorrect.'] } }))
    await afficherProfil(CLIENT_CONNECTE)

    await user.type(screen.getByLabelText('Mot de passe', { selector: '#champ-mot_de_passe_suppression' }), MOT_DE_PASSE)
    await user.click(screen.getByRole('button', { name: 'Supprimer mon compte' }))
    const fenetre = screen.getByRole('alertdialog')
    expect(fenetre).not.toHaveTextContent('annonces')
    await user.click(within(fenetre).getByRole('button', { name: 'Supprimer mon compte' }))

    expect(await screen.findByText('Mot de passe incorrect.')).toHaveAttribute('id', 'erreur-mot_de_passe_suppression')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent('/profil')
  })
})

describe('Session au démarrage et fiche publique', () => {
  it("lit la session auprès de l'API au démarrage (aucun jeton côté navigateur)", async () => {
    let resoudre
    obtenirSession.mockReturnValue(new Promise((r) => (resoudre = r)))
    render(
      <MemoryRouter initialEntries={['/profil']}>
        <FournisseurAuth>
          <App />
        </FournisseurAuth>
      </MemoryRouter>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Vérification de la session…')
    resoudre(PROPRIETAIRE_CONNECTE)
    expect(await screen.findByRole('heading', { level: 1, name: 'Loujain Rouached' })).toBeInTheDocument()
    expect(obtenirSession).toHaveBeenCalledTimes(1)
    expect(localStorage.length).toBe(0)
  })

  it('affiche le prénom et la photo du propriétaire sur la fiche publique', async () => {
    obtenirAnnonce.mockResolvedValue({
      ...STUDIO, statut: 'publiee', proprietaire: { prenom: 'Loujain', photo_profil: '/uploads/moi.jpg' },
    })
    afficherApp('/annonces/7', { utilisateur: null })

    const bloc = (await screen.findByText('Proposé par', { exact: false })).closest('.fiche__proprietaire')
    expect(bloc).toHaveTextContent('Proposé par Loujain')
    expect(bloc.querySelector('img')).toHaveAttribute('src', '/uploads/moi.jpg')
  })
})
