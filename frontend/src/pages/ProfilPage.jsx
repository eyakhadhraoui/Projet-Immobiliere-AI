import Avatar from '../components/Avatar'
import BadgeVerification from '../components/BadgeVerification'
import ProfilInformations from '../components/ProfilInformations'
import ProfilMotDePasse from '../components/ProfilMotDePasse'
import ProfilPhoto from '../components/ProfilPhoto'
import HistoriqueConnexions from '../components/HistoriqueConnexions'
import ProfilZoneDanger from '../components/ProfilZoneDanger'
import { useAuth } from '../hooks/useAuth'
import { LIBELLES_ROLE } from '../utils/compte'
import { formaterDate } from '../utils/format'

/** Page « Mon profil » (utilisateur connecté). */
export default function ProfilPage() {
  const { utilisateur } = useAuth()

  return (
    <section className="page profil">
      <div className="profil__entete">
        <Avatar utilisateur={utilisateur} taille="grand" />
        <div>
          <h1>
            {utilisateur.prenom} {utilisateur.nom}
          </h1>
          <p className="profil__sous-titre">
            <span className="badge">{LIBELLES_ROLE[utilisateur.role] ?? utilisateur.role}</span>
            {utilisateur.created_at && <span> Membre depuis le {formaterDate(utilisateur.created_at)}</span>}
          </p>
        </div>
      </div>

      <div className="profil__colonnes">
        <div className="profil__principal">
          <ProfilInformations />
          <ProfilMotDePasse />
        </div>
        <div className="profil__lateral">
          <HistoriqueConnexions />
          <ProfilPhoto />
          <section className="panneau profil__section" aria-labelledby="titre-verifications">
            <h2 id="titre-verifications">Vérification d'identité</h2>
            <div className="verifications">
              <BadgeVerification libelle="CIN" verifie={utilisateur.cin_verifiee} />
              <BadgeVerification libelle="Visage" verifie={utilisateur.visage_verifie} />
            </div>
            <p className="champ__aide">
              La vérification automatique de la CIN et du visage arrive bientôt. Un profil vérifié inspirera
              davantage confiance aux autres utilisateurs.
            </p>
          </section>
          <ProfilZoneDanger />
        </div>
      </div>
    </section>
  )
}
