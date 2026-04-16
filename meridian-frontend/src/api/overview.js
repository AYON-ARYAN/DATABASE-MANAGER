import api from './client'

export const getOverview = () =>
  api.post('/api/overview').then(r => r.data)

export const getErDiagram = () =>
  api.post('/api/er-diagram').then(r => r.data)

export const runOverviewQuery = (query) =>
  api.post('/api/overview/query', { query }).then(r => r.data)
