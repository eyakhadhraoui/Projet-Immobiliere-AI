import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fichierImage } from '../test/apiSimulee'
import GestionPhotos from './GestionPhotos'

/** GestionPhotos avec l'état des fichiers en attente, comme dans les pages. */
function AvecEtat({ photos = [] }) {
  const [fichiers, setFichiers] = useState([])
  return <GestionPhotos photos={photos} fichiers={fichiers} onChangerFichiers={setFichiers} />
}

const photosExistantes = (n) =>
  Array.from({ length: n }, (_, i) => ({ id: i + 1, annonce_id: 1, ordre: i + 1, url: `/uploads/${i + 1}.jpg` }))

// applyAccept: false → le fichier refusé atteint bien le composant (sinon user-event le filtre selon "accept").
const utilisateur = () => userEvent.setup({ delay: null, applyAccept: false })

describe('GestionPhotos', () => {
  it('refuse un format invalide avant envoi', async () => {
    const user = utilisateur()
    render(<AvecEtat />)

    await user.upload(screen.getByLabelText('Ajouter des photos'), [
      fichierImage('plan.pdf', 1024, 'application/pdf'),
      fichierImage('anime.gif', 1024, 'image/gif'),
      fichierImage('salon.jpg'),
    ])

    const alerte = screen.getByRole('alert')
    expect(alerte).toHaveTextContent('plan.pdf : format non accepté (formats autorisés : jpg, jpeg, png, webp).')
    expect(alerte).toHaveTextContent('anime.gif : format non accepté')
    expect(screen.getByLabelText('Ajouter des photos')).toHaveAttribute('aria-invalid', 'true')
    // La sélection est refusée en entier : aucun aperçu, même pour le fichier valide.
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Photos (0/10)' })).toBeInTheDocument()
  })

  it('limite le total à 10 photos (enregistrées + en attente)', async () => {
    const user = utilisateur()
    render(<AvecEtat photos={photosExistantes(8)} />)

    await user.upload(screen.getByLabelText('Ajouter des photos'), [
      fichierImage('1.jpg'),
      fichierImage('2.jpg'),
      fichierImage('3.jpg'),
    ])
    expect(screen.getByRole('alert')).toHaveTextContent('Maximum 10 photos par annonce : vous pouvez encore en ajouter 2.')
    expect(screen.queryByRole('img', { name: /^Aperçu/ })).not.toBeInTheDocument()

    await user.upload(screen.getByLabelText('Ajouter des photos'), [fichierImage('1.jpg'), fichierImage('2.jpg')])
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: /^Aperçu/ })).toHaveLength(2)
    expect(screen.getByRole('group', { name: 'Photos (10/10)' })).toBeInTheDocument()
    expect(screen.getByLabelText('Ajouter des photos')).toBeDisabled()
  })

  it('refuse une sélection de plus de 5 Mo au total', async () => {
    const user = utilisateur()
    render(<AvecEtat />)

    await user.upload(screen.getByLabelText('Ajouter des photos'), [
      fichierImage('a.jpg', 3 * 1024 * 1024),
      fichierImage('b.jpg', 3 * 1024 * 1024),
    ])

    expect(screen.getByRole('alert')).toHaveTextContent('Les photos à envoyer pèsent 6 Mo : 5 Mo maximum par envoi.')
  })

  it('prévisualise les photos choisies et permet de les retirer', async () => {
    const user = utilisateur()
    render(<AvecEtat />)

    await user.upload(screen.getByLabelText('Ajouter des photos'), [fichierImage('salon.jpg'), fichierImage('cuisine.png')])
    expect(screen.getByRole('img', { name: 'Aperçu : salon.jpg' })).toHaveAttribute('src', expect.stringMatching(/^blob:/))

    await user.click(screen.getByRole('button', { name: 'Retirer salon.jpg' }))

    expect(screen.queryByRole('img', { name: 'Aperçu : salon.jpg' })).not.toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Aperçu : cuisine.png' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Photos (1/10)' })).toBeInTheDocument()
  })

  it("n'affiche pas les boutons d'ordre ni de suppression sans les actions correspondantes", () => {
    render(<AvecEtat photos={photosExistantes(2)} />)
    expect(screen.getAllByRole('img', { name: /^Photo \d de l'annonce$/ })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /Monter|Descendre|Supprimer/ })).not.toBeInTheDocument()
  })
})
