import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ajouterPhotos, creerAnnonce, enregistrerDisponibilitesVisite, lireErreur } from '../api/annonces'
import AnnonceForm from '../components/AnnonceForm'
import GestionPhotos from '../components/GestionPhotos'
import { decrireEchecPhotos } from '../utils/photos'

/** Création d'une annonce (toujours en brouillon), puis envoi des photos choisies. */
export default function NouvelleAnnoncePage() {
  const navigate = useNavigate()
  const [fichiers, setFichiers] = useState([])

  async function creer(donnees, disponibilites) {
    let annonce
    try {
      annonce = await creerAnnonce(donnees) // propriétaire = compte connecté (côté API)
    } catch (error) {
      return lireErreur(error)
    }

    const detail = `/espace/annonces/${annonce.id}`
    if (fichiers.length > 0) {
      try {
        await ajouterPhotos(annonce.id, fichiers)
      } catch (error) {
        // L'annonce existe déjà : on ne reste pas sur le formulaire (un nouvel envoi créerait un doublon).
        navigate(detail, { state: { avertissement: decrireEchecPhotos("L'annonce a été créée en brouillon", error) } })
        return null
      }
      if (disponibilites?.length > 0) {
        try {
          await enregistrerDisponibilitesVisite(annonce.id, disponibilites)
        } catch (error) {
          navigate(detail, { state: { avertissement: `Annonce créée, mais les disponibilités n'ont pas été enregistrées : ${lireErreur(error).message}` } })
          return null
        }
      }
    }

    const photos = fichiers.length > 0 ? ` avec ${fichiers.length} photo${fichiers.length > 1 ? 's' : ''}` : ''
    navigate(detail, { state: { succes: `Annonce créée en brouillon${photos}.` } })
    return null
  }

  return (
    <section className="page">
      <h1>Nouvelle annonce</h1>
      <p className="page__intro">Les champs marqués d'un * sont obligatoires. L'annonce est créée en brouillon.</p>
      <AnnonceForm onSoumettre={creer} libelleBouton="Créer l'annonce">
        <GestionPhotos fichiers={fichiers} onChangerFichiers={setFichiers} />
      </AnnonceForm>
    </section>
  )
}
