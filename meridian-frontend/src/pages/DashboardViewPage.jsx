import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import { Select, Textarea } from '../components/ui/Input'
import ChartWrapper from '../components/charts/ChartWrapper'
import ResultsTable from '../components/data/ResultsTable'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useToast } from '../context/ToastContext'
import { useDb } from '../context/DbContext'
import { getDashboard, addWidget, removeWidget } from '../api/dashboards'
import { runRawQuery } from '../api/query'
import { getTablesList } from '../api/analysis'
import { ArrowLeft, Plus, Trash2, BarChart3 } from 'lucide-react'

export default function DashboardViewPage() {
  const { id } = useParams()
  const toast = useToast()
  const { activeDb } = useDb()
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [widgetData, setWidgetData] = useState({})
  const [newWidget, setNewWidget] = useState({ title: '', query: '', chart_type: 'bar' })
  const [tables, setTables] = useState([])

  const load = useCallback(async () => {
    try {
      const data = await getDashboard(id)
      setDashboard(data)
      // Load data for each widget
      for (const w of (data.widgets || [])) {
        runRawQuery(w.query, w.db_name || activeDb)
          .then(res => setWidgetData(prev => ({ ...prev, [w.id]: res })))
          .catch(() => setWidgetData(prev => ({ ...prev, [w.id]: { error: 'Query failed' } })))
      }
    } catch { toast.error('Failed to load dashboard') }
    setLoading(false)
  }, [id, activeDb, toast])

  useEffect(() => { load() }, [load])

  const handleAddWidget = async () => {
    if (!newWidget.title || !newWidget.query) return
    try {
      await addWidget(id, newWidget.title, newWidget.query, newWidget.chart_type, activeDb)
      setShowAdd(false)
      setNewWidget({ title: '', query: '', chart_type: 'bar' })
      toast.success('Widget added')
      load()
    } catch { toast.error('Failed to add widget') }
  }

  const handleRemoveWidget = async (widgetId) => {
    try {
      await removeWidget(id, widgetId)
      toast.success('Widget removed')
      load()
    } catch { toast.error('Failed to remove widget') }
  }

  const openAddModal = async () => {
    setShowAdd(true)
    try {
      const data = await getTablesList()
      setTables(data.tables || [])
    } catch {}
  }

  if (loading) return <AppShell><LoadingSpinner text="Loading dashboard..." /></AppShell>
  if (!dashboard) return <AppShell><p className="text-zinc-400">Dashboard not found</p></AppShell>

  return (
    <AppShell wide>
      <div className="space-y-6 animate-fade-up">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/dashboards" className="p-2 hover:bg-white/5 rounded-lg transition-colors">
              <ArrowLeft className="w-4 h-4 text-zinc-400" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-zinc-100">{dashboard.name}</h1>
              <p className="text-sm text-zinc-500">{dashboard.widgets?.length || 0} widgets</p>
            </div>
          </div>
          <Button onClick={openAddModal} size="sm">
            <Plus className="w-4 h-4" /> Add Widget
          </Button>
        </div>

        {/* Widget Grid */}
        <div className="grid md:grid-cols-2 gap-4">
          {(dashboard.widgets || []).map(w => {
            const data = widgetData[w.id]
            return (
              <div key={w.id} className="glass rounded-xl p-5 group">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-200">{w.title}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">{w.chart_type}</span>
                      <span className="text-[10px] text-zinc-600">{w.db_name}</span>
                    </div>
                  </div>
                  <button onClick={() => handleRemoveWidget(w.id)} className="p-1 opacity-0 group-hover:opacity-100 hover:bg-rose-500/10 rounded transition-all cursor-pointer">
                    <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                  </button>
                </div>
                <div className="mt-2">
                  {!data ? <LoadingSpinner size="sm" /> :
                    data.error ? <p className="text-xs text-rose-400">{data.error}</p> :
                    w.chart_type === 'table' ? (
                      <ResultsTable columns={data.columns || []} rows={data.rows || []} maxHeight="250px" />
                    ) : (
                      <ChartWrapper
                        type={w.chart_type}
                        labels={(data.rows || []).map(r => String(r[0]))}
                        data={(data.rows || []).map(r => Number(r[1]) || 0)}
                        height={220}
                      />
                    )
                  }
                </div>
              </div>
            )
          })}
        </div>

        {(dashboard.widgets || []).length === 0 && (
          <div className="text-center py-16">
            <BarChart3 className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
            <p className="text-zinc-400">No widgets yet. Add one to get started.</p>
          </div>
        )}

        {/* Add Widget Modal */}
        <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Add Widget">
          <div className="space-y-4">
            <Input label="Widget Title" value={newWidget.title} onChange={e => setNewWidget(p => ({ ...p, title: e.target.value }))} placeholder="e.g. Revenue by Month" />
            <Select
              label="Chart Type"
              value={newWidget.chart_type}
              onChange={e => setNewWidget(p => ({ ...p, chart_type: e.target.value }))}
              options={[
                { value: 'bar', label: 'Bar Chart' },
                { value: 'line', label: 'Line Chart' },
                { value: 'pie', label: 'Pie Chart' },
                { value: 'doughnut', label: 'Doughnut Chart' },
                { value: 'table', label: 'Data Table' },
              ]}
            />
            {tables.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Quick: Select Table</label>
                <div className="grid grid-cols-3 gap-1.5 max-h-32 overflow-y-auto">
                  {tables.map(t => (
                    <button
                      key={t.name}
                      onClick={() => setNewWidget(p => ({ ...p, query: `SELECT * FROM "${t.name}" LIMIT 50`, title: p.title || t.name }))}
                      className="text-left px-2 py-1.5 rounded bg-white/5 text-xs text-zinc-400 hover:bg-white/10 transition-colors cursor-pointer truncate"
                    >
                      {t.name} <span className="text-zinc-600">({t.rows})</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <Textarea label="SQL Query" value={newWidget.query} onChange={e => setNewWidget(p => ({ ...p, query: e.target.value }))} placeholder="SELECT label, value FROM ..." rows={3} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
              <Button onClick={handleAddWidget}>Add Widget</Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  )
}
