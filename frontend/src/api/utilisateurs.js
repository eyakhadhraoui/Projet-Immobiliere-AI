import { api } from './client'

/** GET /api/utilisateurs — liste des comptes, filtrable par rôle. */
export async function listerUtilisateurs(params = {}) {
  const { data } = await api.get('/utilisateurs', { params })
  return data
}
