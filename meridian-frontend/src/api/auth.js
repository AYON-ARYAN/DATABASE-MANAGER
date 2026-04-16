import api from './client'

export const login = (username, password) =>
  api.post('/api/auth/login', { username, password }).then(r => r.data)

export const logout = () =>
  api.post('/api/auth/logout').then(r => r.data)

export const getSession = () =>
  api.get('/api/auth/session').then(r => r.data)
