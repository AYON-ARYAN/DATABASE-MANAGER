import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Select } from '../components/ui/Input'
import { useDb } from '../context/DbContext'
import { useToast } from '../context/ToastContext'
import { getConnections, addConnection, deleteConnection, testConnection, getDbTypes } from '../api/databases'
import { Database, Plus, Trash2, Zap, Check, X, Plug } from 'lucide-react'

export default function DatabasesPage() {
  const { activeDb, switchDb, refreshConnections } = useDb()
  const toast = useToast()
  const [connections, setConnections] = useState([])
  const [dbTypes, setDbTypes] = useState({})
  const [dbFields, setDbFields] = useState({})
  const [dbDisplayNames, setDbDisplayNames] = useState({})
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState({})
  const [testResults, setTestResults] = useState({})

  // New connection form
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState('')
  const [formType, setFormType] = useState('sqlite')
  const [formFields, setFormFields] = useState({})
  const [adding, setAdding] = useState(false)

  const load = useCallback(async () => {
    try {
      const [connData, typeData] = await Promise.all([
        getConnections(),
        getDbTypes()
      ])
      setConnections(connData.connections || [])
      setDbTypes(typeData.db_types || {})
      setDbFields(typeData.db_fields || {})
      setDbDisplayNames(typeData.db_display_names || {})
    } catch { toast.error('Failed to load connections') }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleTest = async (name) => {
    setTesting(p => ({ ...p, [name]: true }))
    try {
      const data = await testConnection(name)
      setTestResults(p => ({ ...p, [name]: data }))
      if (data.success) toast.success(`${name}: Connected!`)
      else toast.error(`${name}: ${data.error || 'Failed'}`)
    } catch { toast.error('Test failed') }
    setTesting(p => ({ ...p, [name]: false }))
  }

  const handleDelete = async (name) => {
    try {
      await deleteConnection(name)
      toast.success('Connection deleted')
      refreshConnections()
      load()
    } catch { toast.error('Failed to delete') }
  }

  const handleAdd = async () => {
    if (!formName.trim()) { toast.error('Name required'); return }
    setAdding(true)
    try {
      const data = await addConnection(formName, formType, formFields)
      if (data.success) {
        toast.success(data.message || 'Connection added')
        setShowForm(false)
        setFormName('')
        setFormFields({})
        refreshConnections()
        load()
      } else {
        toast.error(data.message || 'Failed to add')
      }
    } catch (err) { toast.error('Failed to add connection') }
    setAdding(false)
  }

  const currentFields = dbFields[formType] || []

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">Database Connections</h1>
            <p className="text-sm text-zinc-500">Manage your database connections</p>
          </div>
          <div className="flex gap-2">
            <Link to="/create-database">
              <Button variant="secondary" size="sm"><Database className="w-4 h-4" /> Create DB</Button>
            </Link>
            <Button onClick={() => setShowForm(!showForm)} size="sm">
              <Plus className="w-4 h-4" /> Add Connection
            </Button>
          </div>
        </div>

        {/* Connections List */}
        <div className="space-y-3">
          {connections.map(c => (
            <div key={c.name} className={`glass rounded-xl p-4 transition-all ${c.name === activeDb ? 'border-blue-500/30 glow-blue' : ''}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${c.name === activeDb ? 'bg-blue-500/20' : 'bg-white/5'}`}>
                    <Database className={`w-4 h-4 ${c.name === activeDb ? 'text-blue-400' : 'text-zinc-500'}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-200">{c.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">{dbDisplayNames[c.db_type] || c.db_type}</span>
                      {c.name === activeDb && <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">Active</span>}
                    </div>
                    <div className="text-[10px] text-zinc-600 mt-0.5">
                      {Object.entries(c.config || {}).filter(([k]) => k !== 'password').map(([k, v]) => `${k}: ${v}`).join(' | ')}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {testResults[c.name] && (
                    testResults[c.name].success
                      ? <Check className="w-4 h-4 text-emerald-400" />
                      : <X className="w-4 h-4 text-rose-400" />
                  )}
                  <Button variant="ghost" size="sm" onClick={() => handleTest(c.name)} loading={testing[c.name]}>
                    <Zap className="w-3 h-3" /> Test
                  </Button>
                  {c.name !== activeDb && (
                    <Button variant="secondary" size="sm" onClick={() => switchDb(c.name)}>
                      <Plug className="w-3 h-3" /> Use
                    </Button>
                  )}
                  {c.name !== 'Default SQLite' && (
                    <Button variant="danger" size="sm" onClick={() => handleDelete(c.name)}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add Connection Form */}
        {showForm && (
          <div className="glass rounded-xl p-5 border-l-4 border-blue-500 animate-fade-up">
            <h3 className="text-sm font-semibold text-zinc-200 mb-4">Add New Connection</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <Input label="Connection Name" value={formName} onChange={e => setFormName(e.target.value)} placeholder="My Database" />
              <Select
                label="Database Type"
                value={formType}
                onChange={e => { setFormType(e.target.value); setFormFields({}) }}
                options={Object.entries(dbDisplayNames).map(([k, v]) => ({ value: k, label: v }))}
              />
              {currentFields.map(f => (
                <Input
                  key={f.name}
                  label={f.label || f.name}
                  type={f.name === 'password' ? 'password' : 'text'}
                  value={formFields[f.name] || ''}
                  onChange={e => setFormFields(p => ({ ...p, [f.name]: e.target.value }))}
                  placeholder={f.placeholder || f.default || ''}
                />
              ))}
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button onClick={handleAdd} loading={adding}>Save Connection</Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
