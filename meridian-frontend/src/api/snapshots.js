import api from './client'

export const getSnapshots = () =>
  api.get('/api/snapshots').then(r => r.data)

export const createSnapshot = () =>
  api.post('/api/snapshots').then(r => r.data)

export const restoreSnapshot = (snapId, connectionName) =>
  api.post('/api/snapshots/restore', { snap_id: snapId, connection_name: connectionName }).then(r => r.data)

export const deleteSnapshot = (snapId) =>
  api.delete(`/api/snapshots/${snapId}`).then(r => r.data)

export const undoLast = () =>
  api.post('/api/undo').then(r => r.data)
