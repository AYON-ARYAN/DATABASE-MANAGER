import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import * as dbApi from '../api/databases'
import { useAuth } from './AuthContext'

const DbContext = createContext(null)

export function DbProvider({ children }) {
  const { user } = useAuth()
  const [activeDb, setActiveDb] = useState(null)
  const [connections, setConnections] = useState([])
  const [dbInfo, setDbInfo] = useState(null)
  const [llmProvider, setLlmProvider] = useState('mistral')

  const refreshConnections = useCallback(async () => {
    if (!user) return
    try {
      const data = await dbApi.getConnections()
      setConnections(data.connections || [])
      setActiveDb(data.active_db || 'Default SQLite')
      setDbInfo(data.db_info || null)
      if (data.llm_provider) setLlmProvider(data.llm_provider)
    } catch (e) {
      console.error('Failed to load connections', e)
    }
  }, [user])

  useEffect(() => {
    refreshConnections()
  }, [refreshConnections])

  const switchDb = useCallback(async (name) => {
    const data = await dbApi.selectConnection(name)
    if (data.success) {
      setActiveDb(name)
      setDbInfo(data.db_info || null)
    }
    return data
  }, [])

  return (
    <DbContext.Provider value={{
      activeDb, connections, dbInfo, llmProvider,
      setLlmProvider, switchDb, refreshConnections
    }}>
      {children}
    </DbContext.Provider>
  )
}

export function useDb() {
  const ctx = useContext(DbContext)
  if (!ctx) throw new Error('useDb must be used within DbProvider')
  return ctx
}
