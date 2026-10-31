import { api } from './client'

export async function listerMaintenance(params = {}) {
  const { data } = await api.get('/maintenance', { params })
  return data
}

export async function obtenirMaintenance(id) {
  const { data } = await api.get(`/maintenance/${id}`)
  return data
}

export async function locationsActivesMaintenance() {
  const { data } = await api.get('/maintenance/locations-actives')
  return data.items
}

export async function signalerMaintenance(donnees, fichiers = []) {
  const form = new FormData()
  form.append('donnees', JSON.stringify(donnees))
  fichiers.forEach((fichier) => form.append('photos', fichier))
  const { data } = await api.post('/maintenance', form)
  return data
}

export async function analyserPhotoMaintenance(photo, locationId) {
  const form = new FormData()
  form.append('photo', photo)
  form.append('location_id', String(locationId))
  const { data } = await api.post('/maintenance/ia/analyze-photo', form)
  return data
}

export async function diagnostiquerMaintenance(donnees) {
  const { data } = await api.post('/maintenance/ia/diagnose', donnees)
  return data
}

export async function agirMaintenance(id, donnees) {
  const { data } = await api.patch(`/maintenance/${id}`, donnees)
  return data
}

export async function listerNotificationsMaintenance() {
  const { data } = await api.get('/maintenance/notifications')
  return data
}

export async function marquerNotificationMaintenanceLue(id) {
  const { data } = await api.patch(`/maintenance/notifications/${id}/lue`)
  return data
}
