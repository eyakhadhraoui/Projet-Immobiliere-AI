import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ajouterPhotos, enregistrerDisponibilitesVisite, lireErreur, modifierAnnonce, reordonnerPhotos, supprimerPhoto } from '../api/annonces'
import AnnonceForm from '../components/AnnonceForm'
import GestionPhotos from '../components/GestionPhotos'
import MessageErreur from '../components/MessageErreur'
import { useAnnonce } from '../hooks/useAnnonce'
import { champsModifies, versApi, versFormulaire } from '../utils/annonceForm'
import { decrireEchecPhotos } from '../utils/photos'
import PageIntrouvable from './PageIntrouvable'

function decrireEnregistrement(aModifie, nbPhotos) {
  const photos = `${nbPhotos} photo${nbPhotos > 1 ? 's' : ''} ajoutée${nbPhotos > 1 ? 's' : ''}`
  if (aModifie && nbPhotos > 0) return `Annonce modifiée et ${photos}.`
  if (aModifie) return 'Annonce modifiée.'
  if (nbPhotos > 0) return `${photos.charAt(0).toUpperCase()}${photos.slice(1)}.`
  return "Aucune modification : l'annonce est inchangée."
}

/**
 * Modification d'une annonce : formulaire prérempli, PUT limité aux champs modifiés,
 * envoi des nouvelles photos à l'enregistrement ; suppression et ordre des photos immédiats.
 */
export default function ModifierAnnoncePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { etat, annonce, erreur, reessayer, remplacerAnnonce } = useAnnonce(id, true)
  const [fichiers, setFichiers] = useState([])
  const disponibilites = annonce?.disponibilites || []

  if (etat === 'introuvable') {
    return (
      <PageIntrouvable
        titre="Annonce introuvable"
        message={`L'annonce n° ${id} n'existe pas ou a été supprimée.`}
        lien={{ to: '/espace/annonces', libelle: '← Retour à mes annonces' }}
      />
    )
  }

  const detail = `/espace/annonces/${id}`

  async function enregistrer(donnees, disponibilites) {
    const modifications = champsModifies(versApi(versFormulaire(annonce)), donnees)
    const aModifie = Object.keys(modifications).length > 0

    if (aModifie) {
      try {
        await modifierAnnonce(id, modifications)
      } catch (error) {
        return lireErreur(error)
      }
    }

    if (fichiers.length > 0) {
      try {
        await ajouterPhotos(id, fichiers)
      } catch (error) {
        // Rien d'autre n'a été enregistré : on reste sur le formulaire avec l'erreur.
        if (!aModifie) return lireErreur(error)
        navigate(detail, { state: { avertissement: decrireEchecPhotos("L'annonce a été modifiée", error) } })
        return null
      }
      if (disponibilites?.length > 0) {
        try {
          await enregistrerDisponibilitesVisite(id, disponibilites)
        } catch (error) {
          if (!aModifie && fichiers.length === 0) return lireErreur(error)
          navigate(detail, { state: { avertissement: `Annonce enregistrée, mais les disponibilités n'ont pas été enregistrées : ${lireErreur(error).message}` } })
          return null
        }
      }
    }

    navigate(detail, { state: { succes: decrireEnregistrement(aModifie, fichiers.length) } })
    return null
  }

  async function supprimerUnePhoto(photo) {
    await supprimerPhoto(id, photo.id)
    remplacerAnnonce((a) => ({ ...a, photos: a.photos.filter((p) => p.id !== photo.id) }))
  }

  async function reordonner(ids) {
    const { photos } = await reordonnerPhotos(id, ids)
    remplacerAnnonce((a) => ({ ...a, photos }))
  }

  return (
    <section className="page">
      <h1>Modifier l'annonce</h1>

      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement de l'annonce…
        </p>
      )}

      {etat === 'erreur' && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && (
        <>
          <p className="page__intro">
            <Link to={detail}>← {annonce.titre}</Link> — seuls les champs modifiés seront enregistrés.
          </p>
          <AnnonceForm key={annonce.id} valeursInitiales={{ ...versFormulaire(annonce), disponibilites }} onSoumettre={enregistrer} libelleBouton="Enregistrer">
            <GestionPhotos
              photos={annonce.photos ?? []}
              fichiers={fichiers}
              onChangerFichiers={setFichiers}
              onSupprimerPhoto={supprimerUnePhoto}
              onReordonner={reordonner}
            />
          </AnnonceForm>
        </>
      )}
    </section>
  )
}
