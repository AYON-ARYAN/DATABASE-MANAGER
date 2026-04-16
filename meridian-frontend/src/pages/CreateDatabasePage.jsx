import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Select } from '../components/ui/Input'
import { useToast } from '../context/ToastContext'
import { getDbTypes, createDatabase } from '../api/databases'
import { Database, Plus, Trash2 } from 'lucide-react'

export default function CreateDatabasePage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [dbDisplayNames, setDbDisplayNames] = useState({})
  const [dbName, setDbName] = useState('')
  const [dbType, setDbType] = useState('sqlite')
  const [serverFields, setServerFields] = useState({})
  const [tables, setTables] = useState([])
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    getDbTypes().then(data => setDbDisplayNames(data.db_display_names || {})).catch(() => {})
  }, [])

  const addTable = () => {
    setTables(prev => [...prev, { name: '', columns: [{ name: '', type: 'TEXT', pk: false, not_null: false }] }])
  }

  const removeTable = (idx) => setTables(prev => prev.filter((_, i) => i !== idx))

  const updateTable = (idx, field, val) => {
    setTables(prev => prev.map((t, i) => i === idx ? { ...t, [field]: val } : t))
  }

  const addColumn = (tIdx) => {
    setTables(prev => prev.map((t, i) => i === tIdx ? { ...t, columns: [...t.columns, { name: '', type: 'TEXT', pk: false, not_null: false }] } : t))
  }

  const updateColumn = (tIdx, cIdx, field, val) => {
    setTables(prev => prev.map((t, i) =>
      i === tIdx ? { ...t, columns: t.columns.map((c, j) => j === cIdx ? { ...c, [field]: val } : c) } : t
    ))
  }

  const handleCreate = async () => {
    if (!dbName.trim()) { toast.error('Database name required'); return }
    setCreating(true)
    try {
      const data = await createDatabase({ db_name: dbName, db_type: dbType, tables, ...serverFields })
      if (data.success) {
        toast.success(data.message || 'Database created!')
        navigate('/databases')
      } else {
        toast.error(data.error || 'Failed to create')
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Creation failed')
    }
    setCreating(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up max-w-3xl mx-auto">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Database className="w-6 h-6 text-blue-400" /> Create Database
          </h1>
          <p className="text-sm text-zinc-500">Create a new database from scratch</p>
        </div>

        <div className="glass rounded-xl p-5">
          <div className="grid md:grid-cols-2 gap-4">
            <Input label="Database Name" value={dbName} onChange={e => setDbName(e.target.value)} placeholder="my_database" />
            <Select
              label="Database Type"
              value={dbType}
              onChange={e => setDbType(e.target.value)}
              options={Object.entries(dbDisplayNames).map(([k, v]) => ({ value: k, label: v }))}
            />
          </div>
          {dbType !== 'sqlite' && (
            <div className="grid md:grid-cols-2 gap-4 mt-4">
              <Input label="Host" value={serverFields.host || ''} onChange={e => setServerFields(p => ({ ...p, host: e.target.value }))} placeholder="localhost" />
              <Input label="Port" value={serverFields.port || ''} onChange={e => setServerFields(p => ({ ...p, port: e.target.value }))} placeholder="5432" />
              <Input label="Username" value={serverFields.username || ''} onChange={e => setServerFields(p => ({ ...p, username: e.target.value }))} placeholder="postgres" />
              <Input label="Password" type="password" value={serverFields.password || ''} onChange={e => setServerFields(p => ({ ...p, password: e.target.value }))} />
            </div>
          )}
        </div>

        {/* Tables */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-zinc-200">Tables (Optional)</h3>
            <Button variant="secondary" size="sm" onClick={addTable}>
              <Plus className="w-3 h-3" /> Add Table
            </Button>
          </div>

          {tables.map((table, tIdx) => (
            <div key={tIdx} className="glass rounded-xl p-4 mb-3">
              <div className="flex items-center justify-between mb-3">
                <Input
                  value={table.name}
                  onChange={e => updateTable(tIdx, 'name', e.target.value)}
                  placeholder="Table name"
                  className="max-w-xs"
                />
                <button onClick={() => removeTable(tIdx)} className="p-1 hover:bg-rose-500/10 rounded cursor-pointer">
                  <Trash2 className="w-4 h-4 text-rose-400" />
                </button>
              </div>

              <div className="space-y-2">
                {table.columns.map((col, cIdx) => (
                  <div key={cIdx} className="flex items-center gap-2">
                    <Input value={col.name} onChange={e => updateColumn(tIdx, cIdx, 'name', e.target.value)} placeholder="Column name" className="flex-1" />
                    <select
                      value={col.type}
                      onChange={e => updateColumn(tIdx, cIdx, 'type', e.target.value)}
                      className="bg-white/5 border border-white/10 rounded-lg px-2 py-2 text-xs text-zinc-300 focus:outline-none"
                    >
                      {['TEXT', 'INTEGER', 'REAL', 'BLOB', 'BOOLEAN', 'DATE', 'DATETIME', 'VARCHAR(255)', 'NUMERIC'].map(t => (
                        <option key={t} value={t} className="bg-zinc-900">{t}</option>
                      ))}
                    </select>
                    <label className="flex items-center gap-1 text-xs text-zinc-400 cursor-pointer">
                      <input type="checkbox" checked={col.pk} onChange={e => updateColumn(tIdx, cIdx, 'pk', e.target.checked)} className="rounded" /> PK
                    </label>
                    <label className="flex items-center gap-1 text-xs text-zinc-400 cursor-pointer">
                      <input type="checkbox" checked={col.not_null} onChange={e => updateColumn(tIdx, cIdx, 'not_null', e.target.checked)} className="rounded" /> NN
                    </label>
                  </div>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={() => addColumn(tIdx)} className="mt-2">
                <Plus className="w-3 h-3" /> Column
              </Button>
            </div>
          ))}
        </div>

        <Button onClick={handleCreate} loading={creating} size="lg" className="w-full">
          Create Database
        </Button>
      </div>
    </AppShell>
  )
}
