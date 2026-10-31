import { useEffect, useId, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Avatar from './Avatar'

/**
 * Bouton avatar + menu du compte (Mon profil, Mon espace pour un propriétaire, Déconnexion).
 * Se ferme avec Échap (le focus revient au bouton) ou par un clic à l'extérieur.
 */
export default function MenuUtilisateur() {
  const { utilisateur, deconnecter } = useAuth()
  const navigate = useNavigate()
  const [ouvert, setOuvert] = useState(false)
  const conteneur = useRef(null)
  const bouton = useRef(null)
  const idMenu = useId()

  useEffect(() => {
    if (!ouvert) return undefined
    function clicExterieur(event) {
      if (!conteneur.current?.contains(event.target)) setOuvert(false)
    }
    document.addEventListener('mousedown', clicExterieur)
    return () => document.removeEventListener('mousedown', clicExterieur)
  }, [ouvert])

  function gererTouche(event) {
    if (event.key === 'Escape' && ouvert) {
      setOuvert(false)
      bouton.current?.focus()
    }
  }

  async function seDeconnecter() {
    setOuvert(false)
    await deconnecter(() => navigate('/', { state: { succes: 'Vous êtes déconnecté.' } }))
  }

  return (
    <div className="menu-compte" ref={conteneur} onKeyDown={gererTouche}>
      <button
        ref={bouton}
        type="button"
        className="menu-compte__bouton"
        aria-expanded={ouvert}
        aria-controls={idMenu}
        onClick={() => setOuvert((o) => !o)}
        aria-label={`${utilisateur.prenom} — menu du compte`}
      >
        <Avatar utilisateur={utilisateur} taille="petit" />
        <span className="menu-compte__nom">{utilisateur.prenom}</span>
        <span aria-hidden="true" className="menu-compte__fleche">▾</span>
      </button>
      {ouvert && (
        <ul className="menu-compte__liste" id={idMenu}>
          <li className="menu-compte__entete" aria-hidden="true">
            {utilisateur.prenom} {utilisateur.nom}
            <br />
            <span>{utilisateur.email}</span>
          </li>
          <li>
            <Link to="/profil" className="menu-compte__lien" onClick={() => setOuvert(false)}>
              Mon profil
            </Link>
          </li>
          {utilisateur.role === 'proprietaire' && (
            <li>
              <Link to="/espace" className="menu-compte__lien" onClick={() => setOuvert(false)}>
                Mon espace
              </Link>
            </li>
          )}
          <li>
            <button type="button" className="menu-compte__lien" onClick={seDeconnecter}>
              Déconnexion
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}
