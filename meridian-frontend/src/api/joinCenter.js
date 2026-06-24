import api from './client'

export const getJoinSchema = () =>
  api.get('/api/join/schema').then(r => r.data)

export const suggestJoins = (leftTable, rightTable) =>
  api.post('/api/join/suggest', { left_table: leftTable, right_table: rightTable }).then(r => r.data)

export const previewJoinSql = (spec) =>
  api.post('/api/join/preview', spec).then(r => r.data)

export const executeJoin = (spec) =>
  api.post('/api/join/execute', spec).then(r => r.data)
