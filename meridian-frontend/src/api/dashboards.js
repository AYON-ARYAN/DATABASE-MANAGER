import api from './client'

export const getDashboards = () =>
  api.get('/api/dashboards').then(r => r.data)

export const createDashboard = (name) =>
  api.post('/api/dashboards', { name }).then(r => r.data)

export const deleteDashboard = (id) =>
  api.delete(`/api/dashboards/${id}`).then(r => r.data)

export const getDashboard = (id) =>
  api.get(`/api/dashboards/${id}`).then(r => r.data)

export const addWidget = (dashId, title, query, chartType, dbName) =>
  api.post(`/api/dashboards/${dashId}/widgets`, {
    title, query, chart_type: chartType, db_name: dbName
  }).then(r => r.data)

export const removeWidget = (dashId, widgetId) =>
  api.delete(`/api/dashboards/${dashId}/widgets/${widgetId}`).then(r => r.data)

export const autoGenerate = (prompt) =>
  api.post('/api/dashboards/auto-generate', { prompt }).then(r => r.data)
