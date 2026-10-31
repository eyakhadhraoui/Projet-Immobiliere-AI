import { Navigate, useParams } from 'react-router-dom'

/** Ancienne URL /annonces/:id/modifier → /espace/annonces/:id/modifier (liens et favoris existants). */
export default function RedirectionModification() {
  const { id } = useParams()
  return <Navigate to={`/espace/annonces/${id}/modifier`} replace />
}
