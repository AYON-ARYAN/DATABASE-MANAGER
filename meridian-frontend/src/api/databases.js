import api from './client'

export const getConnections = () =>
  api.get('/api/connections').then(r => r.data)

export const addConnection = (name, dbType, config) =>
  api.post('/api/connections', { name, db_type: dbType, config }).then(r => r.data)

export const deleteConnection = (name) =>
  api.delete(`/api/connections/${encodeURIComponent(name)}`).then(r => r.data)

export const selectConnection = (name) =>
  api.post('/api/connections/select', { name }).then(r => r.data)

export const testConnection = (name) =>
  api.post('/databases/test', { conn_name: name }, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    transformRequest: [(data) => new URLSearchParams(data).toString()]
  }).then(r => r.data)

export const testNewConnection = (dbType, config) =>
  api.post('/databases/test-new', { db_type: dbType, ...config }, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    transformRequest: [(data) => new URLSearchParams(data).toString()]
  }).then(r => r.data)

export const getDbTypes = () =>
  api.get('/api/db-types').then(r => r.data)

export const createDatabase = (data) =>
  api.post('/api/create-database', data).then(r => r.data)
