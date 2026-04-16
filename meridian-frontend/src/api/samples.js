import api from './client'

export const listSamples = () =>
  api.get('/api/samples').then(r => r.data)

export const installSample = (id) =>
  api.post('/api/samples/install', { id }).then(r => r.data)
