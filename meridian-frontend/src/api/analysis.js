import api from './client'

export const getTablesList = () =>
  api.get('/api/tables-list').then(r => r.data)

export const previewTable = (source, sql) =>
  api.post('/api/table-preview', { source, sql }).then(r => r.data)

export const analyzeDirect = (source, sql, hint) =>
  api.post('/api/analyze-direct', { source, sql, hint }).then(r => r.data)

export const startFullAnalysis = () =>
  api.post('/api/analyze-full').then(r => r.data)

export const getAnalysisStatus = (jobId) =>
  api.get(`/api/analyze-full/status/${jobId}`).then(r => r.data)

export const generateInsights = () =>
  api.post('/api/insights').then(r => r.data)

export const aiAsk = (question) =>
  api.post('/api/ask', { question }).then(r => r.data)
