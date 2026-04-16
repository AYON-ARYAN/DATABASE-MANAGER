import api from './client'

export const runCommand = (command) =>
  api.post('/api/command', { command }).then(r => r.data)

export const paginateResults = (page) =>
  api.get(`/api/command/paginate?page=${page}`).then(r => r.data)

export const executeWrite = (sql) =>
  api.post('/api/execute', { sql }).then(r => r.data)

export const dryRun = (sql) =>
  api.post('/dry-run', { sql }).then(r => r.data)

export const refineQuery = (currentSql, feedback) =>
  api.post('/refine', { current_sql: currentSql, feedback }).then(r => r.data)

export const runRawQuery = (query, dbName) =>
  api.post('/api/query', { query, db_name: dbName }).then(r => r.data)
