import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import BandeauMessages from './components/BandeauMessages'
import AlerteConnexion from './components/AlerteConnexion'
import ChatbotRAG from './components/ChatbotRAG'
import EnTete from './components/EnTete'
import EspaceLayout from './components/EspaceLayout'
import PiedDePage from './components/PiedDePage'
import RouteProtegee from './components/RouteProtegee'
import AccueilPage from './pages/AccueilPage'
import AnnoncePubliquePage from './pages/AnnoncePubliquePage'
import AnnoncesListePage from './pages/AnnoncesListePage'
import VisitesRecherchePage from './pages/VisitesRecherchePage'
import ConnexionPage from './pages/ConnexionPage'
import DetailAnnoncePage from './pages/DetailAnnoncePage'
import GuideDocumentsPage from './pages/GuideDocumentsPage'
import InscriptionPage from './pages/InscriptionPage'
import ModifierAnnoncePage from './pages/ModifierAnnoncePage'
import NouvelleAnnoncePage from './pages/NouvelleAnnoncePage'
import PageIntrouvable from './pages/PageIntrouvable'
import ProfilPage from './pages/ProfilPage'
import RedirectionModification from './pages/RedirectionModification'

import TableauDeBordPage from './pages/espace/TableauDeBordPage'

const HistoriquePage = lazy(() => import('./pages/espace/HistoriquePage'))
const MesAnnoncesPage = lazy(() => import('./pages/espace/MesAnnoncesPage'))
const VisitesPage = lazy(() => import('./pages/espace/visites/VisitesPage'))
const VisiteDetailPage = lazy(() => import('./pages/espace/visites/VisiteDetailPage'))
const VisiteFormPage = lazy(() => import('./pages/espace/visites/VisiteFormPage'))
const TransactionsPage = lazy(() => import('./pages/espace/transactions/TransactionsPage'))
const TransactionDetailPage = lazy(() => import('./pages/espace/transactions/TransactionDetailPage'))
const TransactionFormPage = lazy(() => import('./pages/espace/transactions/TransactionFormPage'))
const ReclamationsPage = lazy(() => import('./pages/espace/ReclamationsPage'))
const LocationsPage = lazy(() => import('./pages/espace/LocationsPage'))
const MaintenancePage = lazy(() => import('./pages/MaintenancePage'))
const MaintenanceDetailPage = lazy(() => import('./pages/MaintenanceDetailPage'))
const MaintenanceNotificationsPage = lazy(() => import('./pages/MaintenanceNotificationsPage'))
const MesLocationsPage = lazy(() => import('./pages/MesLocationsPage'))
const LocationDetailPage = lazy(() => import('./pages/espace/LocationDetailPage'))
const DossiersLitigePage = lazy(() => import('./pages/DossiersLitigePage'))
const RapportInferenceLitigePage = lazy(() => import('./pages/RapportInferenceLitigePage'))

/**
 * Routes de l'application (le Router est fourni par main.jsx, ou par les tests).
 * - site public : accueil, catalogue (annonces publiées), fiche d'une annonce, guide documents & RAG ;
 * - compte : connexion, inscription, profil (connecté) ;
 * - espace propriétaire (/espace, propriétaires connectés) : tableau de bord, gestion des annonces, historique.
 */
export default function App() {
  const chemin = useLocation().pathname
  const estEspace = chemin.startsWith('/espace')
  const estPageGuide = chemin === '/guide-documents'
  const estPageLitige = chemin.startsWith('/dossiers-litige')

  return (
    <div className="site">
      <a className="lien-evitement" href="#contenu">
        Aller au contenu
      </a>
      <EnTete />
      <AlerteConnexion />
      <main id="contenu" className={`contenu${estEspace ? ' contenu--espace' : ''}`} tabIndex={-1}>
        <BandeauMessages />
        <Suspense fallback={<p className="etat" role="status">Chargement de la page…</p>}>
        <Routes>
          <Route path="/" element={<AccueilPage />} />
          <Route path="/annonces" element={<AnnoncesListePage />} />
          <Route path="/visites" element={<VisitesRecherchePage />} />
          <Route path="/annonces/:id" element={<AnnoncePubliquePage />} />
          <Route path="/guide-documents" element={<GuideDocumentsPage />} />
          <Route path="/dossiers-litige" element={<RouteProtegee><DossiersLitigePage /></RouteProtegee>} />
          <Route path="/dossiers-litige/rapport-demo" element={<RouteProtegee><RapportInferenceLitigePage /></RouteProtegee>} />
          <Route path="/maintenance" element={<RouteProtegee><MaintenancePage /></RouteProtegee>} />
          <Route path="/mes-locations" element={<RouteProtegee role="client"><MesLocationsPage /></RouteProtegee>} />
          <Route path="/maintenance/notifications" element={<RouteProtegee><MaintenanceNotificationsPage /></RouteProtegee>} />
          <Route path="/maintenance/:id" element={<RouteProtegee><MaintenanceDetailPage /></RouteProtegee>} />
          {/* Anciennes URL de gestion (FRONT-001 à FRONT-003) */}
          <Route path="/annonces/nouvelle" element={<Navigate to="/espace/annonces/nouvelle" replace />} />
          <Route path="/annonces/:id/modifier" element={<RedirectionModification />} />

          <Route path="/connexion" element={<ConnexionPage />} />
          <Route path="/inscription" element={<InscriptionPage />} />
          <Route
            path="/profil"
            element={
              <RouteProtegee>
                <ProfilPage />
              </RouteProtegee>
            }
          />

          <Route
            path="/espace"
            element={
              <RouteProtegee role="proprietaire">
                <EspaceLayout />
              </RouteProtegee>
            }
          >
            <Route index element={<TableauDeBordPage />} />
            <Route path="annonces" element={<MesAnnoncesPage />} />
            <Route path="annonces/nouvelle" element={<NouvelleAnnoncePage />} />
            <Route path="annonces/:id" element={<DetailAnnoncePage />} />
            <Route path="annonces/:id/modifier" element={<ModifierAnnoncePage />} />
            <Route path="historique" element={<HistoriquePage />} />
            <Route path="visites" element={<VisitesPage />} />
            <Route path="visites/nouvelle" element={<VisiteFormPage />} />
            <Route path="visites/:id" element={<VisiteDetailPage />} />
            <Route path="visites/:id/modifier" element={<VisiteFormPage />} />
            <Route path="transactions" element={<TransactionsPage />} />
            <Route path="transactions/nouvelle" element={<TransactionFormPage />} />
            <Route path="transactions/:id" element={<TransactionDetailPage />} />
            <Route path="transactions/:id/modifier" element={<TransactionFormPage />} />
            <Route path="reclamations" element={<ReclamationsPage />} />
            <Route path="locations" element={<LocationsPage />} />
            <Route path="locations/:id" element={<LocationDetailPage />} />
            <Route path="maintenance" element={<MaintenancePage />} />
            <Route path="maintenance/notifications" element={<MaintenanceNotificationsPage />} />
            <Route path="maintenance/:id" element={<MaintenanceDetailPage />} />
          </Route>

          <Route path="*" element={<PageIntrouvable />} />
        </Routes>
        </Suspense>
        {!estPageGuide && !estPageLitige && <ChatbotRAG modeFlottant={true} />}
      </main>
      <PiedDePage />
    </div>
  )
}
