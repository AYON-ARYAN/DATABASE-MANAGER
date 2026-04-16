import api from './client'

export const getAdminData = () =>
  api.get('/api/admin/metrics').then(r => r.data)

export const updateLlmConfig = (config) =>
  api.post('/admin/llm/config', config).then(r => r.data)

export const pullOllamaModel = (model) =>
  api.post('/admin/ollama/pull', { model }).then(r => r.data)

export const testLlm = (prompt, provider) => {
  const formData = new URLSearchParams()
  formData.append('prompt', prompt)
  formData.append('provider', provider)
  return api.post('/admin/test_llm', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }).then(r => r.data)
}

export const explainCommand = (command) =>
  api.post('/api/intelligence/explain', { command }).then(r => r.data)

export const setProvider = (provider) =>
  api.post('/api/set-provider', { provider }).then(r => r.data)
