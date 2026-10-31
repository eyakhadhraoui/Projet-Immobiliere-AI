import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { changerStatut, demanderRevueFiabilite, lireErreur, listerToutesLesAnnonces, supprimerAnnonce } from '../../api/annonces'
import { analyserAnomalieAnnonce, obtenirEtatFiabilite } from '../../api/ia'
import FenetreConfirmation from '../../components/FenetreConfirmation'
import MessageErreur from '../../components/MessageErreur'
import TableauAnnonces from '../../components/TableauAnnonces'
import { useRequete } from '../../hooks/useRequete'
import { LIBELLES_STATUT } from '../../utils/format'
import { TRI_PAR_DEFAUT, filtrerAnnonces, trierAnnonces } from '../../utils/tableAnnonces'

/**
 * Tableau de toutes les annonces du propriétaire : recherche, filtre par statut, tri par colonne,
 * et actions par ligne (voir, modifier, publier / dépublier, supprimer).
 */
export default function MesAnnoncesPage() {
  const { etat, donnees: annonces, erreur, reessayer, modifierDonnees } = useRequete(
    'toutes-annonces',
    () => listerToutesLesAnnonces({ mes_annonces: true }), // annonces du propriétaire connecté
  )
  const [recherche, setRecherche] = useState('')
  const [statut, setStatut] = useState('')
  const [tri, setTri] = useState(TRI_PAR_DEFAUT)
  const [idEnCours, setIdEnCours] = useState(null)
  const [message, setMessage] = useState(null)
  const [erreurAction, setErreurAction] = useState(null)
  const [aSupprimer, setASupprimer] = useState(null)
  const [analyses, setAnalyses] = useState({})
  const [analyseEnCours, setAnalyseEnCours] = useState(null)
  const [publicationAConfirmer, setPublicationAConfirmer] = useState(null)
  const [etatFiabilite, setEtatFiabilite] = useState(null)

  useEffect(() => {
    let actif = true
    obtenirEtatFiabilite()
      .then((etatMoteur) => { if (actif) setEtatFiabilite(etatMoteur) })
      .catch(() => { if (actif) setEtatFiabilite({ etat: 'inconnu' }) })
    return () => { actif = false }
  }, [])

  async function analyser(annonce) {
    setAnalyseEnCours(annonce.id)
    try {
      const resultat = await analyserAnomalieAnnonce(annonce.id)
      setAnalyses((precedent) => ({ ...precedent, [annonce.id]: resultat }))
    } catch (error) {
      setAnalyses((precedent) => ({ ...precedent, [annonce.id]: { disponible: false, repli: lireErreur(error).message } }))
    } finally {
      setAnalyseEnCours(null)
    }
  }

  function trier(colonne) {
    setTri((actuel) =>
      actuel.colonne === colonne
        ? { colonne, sens: actuel.sens === 'asc' ? 'desc' : 'asc' }
        : { colonne, sens: colonne === 'updated_at' ? 'desc' : 'asc' },
    )
  }

  function remplacer(annonceMaj) {
    modifierDonnees((liste) => liste.map((a) => (a.id === annonceMaj.id ? annonceMaj : a)))
  }

  async function basculerPublication(annonce) {
    const nouveau = annonce.statut === 'publiee' ? 'brouillon' : 'publiee'
    setIdEnCours(annonce.id)
    setMessage(null)
    setErreurAction(null)
    try {
      const annonceMiseAJour = await changerStatut(annonce.id, nouveau)
      remplacer(annonceMiseAJour)
      setMessage(annonceMiseAJour.statut === 'en_attente'
        ? `« ${annonce.titre} » est en attente de vérification. Ce contrôle automatique peut se tromper.`
        : nouveau === 'publiee'
          ? `« ${annonce.titre} » est maintenant publiée.`
          : `« ${annonce.titre} » n'est plus publiée (repassée en brouillon).`)
    } catch (error) {
      if (error?.response?.status === 409 && error?.response?.data?.error === 'confirmation_requise') {
        setPublicationAConfirmer({ annonce, fiabilite: error.response.data.fiabilite })
      } else {
        setErreurAction(`« ${annonce.titre} » : ${lireErreur(error).message}`)
      }
    } finally {
      setIdEnCours(null)
    }
  }

  async function confirmerPublication() {
    const { annonce } = publicationAConfirmer
    setIdEnCours(annonce.id)
    setErreurAction(null)
    try {
      remplacer(await changerStatut(annonce.id, 'publiee', true))
      setMessage(`« ${annonce.titre} » est publiée. Ce contrôle automatique peut se tromper.`)
      setPublicationAConfirmer(null)
    } catch (error) {
      setErreurAction(`« ${annonce.titre} » : ${lireErreur(error).message}`)
    } finally {
      setIdEnCours(null)
    }
  }

  async function demanderRevue(annonce) {
    setIdEnCours(annonce.id)
    setErreurAction(null)
    try {
      const resultat = await demanderRevueFiabilite(annonce.id)
      remplacer({ ...annonce, revue_demandee_le: resultat.revue_demandee_le })
      setMessage('Votre demande de revue a été envoyée.')
    } catch (error) {
      setErreurAction(lireErreur(error).message)
    } finally {
      setIdEnCours(null)
    }
  }

  async function confirmerSuppression() {
    const annonce = aSupprimer
    setIdEnCours(annonce.id)
    setErreurAction(null)
    try {
      await supprimerAnnonce(annonce.id)
      modifierDonnees((liste) => liste.filter((a) => a.id !== annonce.id))
      setMessage(`L'annonce « ${annonce.titre} » a été supprimée.`)
      setASupprimer(null)
    } catch (error) {
      setErreurAction(lireErreur(error).message)
    } finally {
      setIdEnCours(null)
    }
  }

  const listeAnnonces = annonces || []
  const lignes = etat === 'succes' ? trierAnnonces(filtrerAnnonces(listeAnnonces, { recherche, statut }), tri) : []
  const nbPubliees = listeAnnonces.filter((annonce) => annonce.statut === 'publiee').length
  const nbBrouillons = listeAnnonces.filter((annonce) => annonce.statut === 'brouillon').length

  return (
    <section className="page espace-page espace-page--annonces">
      <div className="page__entete espace-page__entete">
        <div><h1>Mes annonces</h1><p className="texte-secondaire">{listeAnnonces.length} annonces · {nbPubliees} publiées · {nbBrouillons} brouillon{nbBrouillons > 1 ? 's' : ''}</p></div>
        <Link to="/espace/annonces/nouvelle" className="bouton bouton--principal">
          Nouvelle annonce
        </Link>
      </div>

      {etat === 'chargement' && (
        <p className="etat" role="status">
          Chargement des annonces…
        </p>
      )}
      {(etat === 'erreur' || etat === 'introuvable') && <MessageErreur erreur={erreur} onReessayer={reessayer} />}

      {etat === 'succes' && (
        <>
          {etatFiabilite && (
            <p className="texte-secondaire" role="status" aria-label="État du contrôle de fiabilité">
              {etatFiabilite.libelle || 'État du contrôle automatique indisponible.'}
              {etatFiabilite.etat === 'indisponible' && ' Les autres vérifications restent actives.'}
            </p>
          )}
          <div className="annonces__onglets" aria-label="Filtrer par statut">
            <button type="button" className={!statut ? 'actif' : ''} onClick={() => setStatut('')}>Toutes · {listeAnnonces.length}</button>
            <button type="button" className={statut === 'publiee' ? 'actif' : ''} onClick={() => setStatut('publiee')}>Publiées · {nbPubliees}</button>
            <button type="button" className={statut === 'brouillon' ? 'actif' : ''} onClick={() => setStatut('brouillon')}>Brouillons · {nbBrouillons}</button>
          </div>
          <div className="barre-outils annonces__filtres" role="search" aria-label="Rechercher dans mes annonces">
            <div className="champ">
              <label htmlFor="mes-annonces-recherche">Rechercher</label>
              <input
                id="mes-annonces-recherche"
                type="search"
                value={recherche}
                onChange={(event) => setRecherche(event.target.value)}
                placeholder="Titre ou ville"
              />
            </div>
            <div className="champ">
              <label htmlFor="mes-annonces-statut">Statut</label>
              <select id="mes-annonces-statut" value={statut} onChange={(event) => setStatut(event.target.value)}>
                <option value="">Tous les statuts</option>
                {Object.entries(LIBELLES_STATUT).map(([valeur, libelle]) => (
                  <option key={valeur} value={valeur}>
                    {libelle}
                  </option>
                ))}
              </select>
            </div>
            <p className="barre-outils__compte" aria-live="polite">
              {lignes.length} {lignes.length > 1 ? 'annonces' : 'annonce'} sur {listeAnnonces.length}
            </p>
          </div>

          {message && (
            <p className="message-succes" role="status">
              {message}
            </p>
          )}
          {erreurAction && !aSupprimer && (
            <p className="champ__erreur" role="alert">
              {erreurAction}
            </p>
          )}

          {listeAnnonces.length === 0 ? (
            <div className="etat etat--vide">
              <p>Vous n'avez encore aucune annonce.</p>
              <Link to="/espace/annonces/nouvelle">Créer ma première annonce</Link>
            </div>
          ) : lignes.length === 0 ? (
            <p className="etat etat--vide">Aucune annonce ne correspond à votre recherche.</p>
          ) : (
            <TableauAnnonces
              annonces={lignes}
              tri={tri}
              onTrier={trier}
              idEnCours={idEnCours}
              onBasculerPublication={basculerPublication}
              onDemanderRevue={demanderRevue}
              onSupprimer={(annonce) => {
                setErreurAction(null)
                setASupprimer(annonce)
              }}
              analyses={analyses}
              analyseEnCours={analyseEnCours}
              onAnalyser={analyser}
            />
          )}
        </>
      )}

      {aSupprimer && (
        <FenetreConfirmation
          titre="Supprimer cette annonce ?"
          message={`L'annonce « ${aSupprimer.titre} » et ses photos seront définitivement supprimées.`}
          libelleConfirmer="Supprimer définitivement"
          libelleEnCours="Suppression…"
          enCours={idEnCours === aSupprimer.id}
          erreur={erreurAction}
          onConfirmer={confirmerSuppression}
          onAnnuler={() => {
            setASupprimer(null)
            setErreurAction(null)
          }}
        />
      )}

      {publicationAConfirmer && (
        <div className="fenetre__fond" onClick={(event) => event.target === event.currentTarget && setPublicationAConfirmer(null)}>
          <section className="fenetre" role="alertdialog" aria-modal="true" aria-labelledby="fiabilite-titre">
            <h2 id="fiabilite-titre">Avant de publier votre annonce</h2>
            <p>Certains éléments méritent une vérification. Vous pouvez modifier l’annonce ou la publier quand même.</p>
            <ul className="fiabilite__raisons">
              {(publicationAConfirmer.fiabilite?.raisons || []).map((raison, index) => (
                <li key={`${raison.signal}-${index}`}>{raison.texte}</li>
              ))}
            </ul>
            {(publicationAConfirmer.fiabilite?.annonces_liees || []).map((lien, index) => (
              lien.url ? <p key={`${lien.annonce_id}-${index}`}>Annonce publique concernée : <Link to={lien.url}>{lien.titre}</Link></p> : null
            ))}
            <p>Si vous publiez quand même, votre confirmation sera enregistrée. Ce contrôle automatique peut se tromper.</p>
            {erreurAction && <p className="champ__erreur" role="alert">{erreurAction}</p>}
            <div className="fenetre__actions">
              <button type="button" className="bouton" onClick={() => setPublicationAConfirmer(null)} disabled={idEnCours !== null}>Annuler</button>
              <button type="button" className="bouton bouton--principal" onClick={confirmerPublication} disabled={idEnCours !== null}>
                {idEnCours !== null ? 'Vérification…' : 'Publier quand même'}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  )
}
