import api from './client'

export const deepAsk = (question, autoRun = true, history = []) =>
  api.post('/api/command-center/deep-ask', { question, auto_run: autoRun, history })
    .then(r => r.data)

export const executeRaw = (sql, takeSnapshot = true) =>
  api.post('/api/command-center/execute-raw', { sql, take_snapshot: takeSnapshot })
    .then(r => r.data)

export const autoInsights = (count = 6, focus = '') =>
  api.post('/api/command-center/auto-insights', { count, focus })
    .then(r => r.data)

export const dataHealth = () =>
  api.post('/api/command-center/data-health').then(r => r.data)

export const fetchKpis = () =>
  api.post('/api/command-center/kpis').then(r => r.data)

export const fetchAnomalies = () =>
  api.post('/api/command-center/anomalies').then(r => r.data)

export const smartPptUrl = () => '/api/command-center/smart-ppt'

export const answerPptUrl = () => '/api/command-center/answer-ppt'
