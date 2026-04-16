import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import EmptyState from '../components/ui/EmptyState'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useToast } from '../context/ToastContext'
import { getDashboards, createDashboard, deleteDashboard, autoGenerate } from '../api/dashboards'
import { BarChart3, Plus, Trash2, ExternalLink, Sparkles, Wand2 } from 'lucide-react'

export default function DashboardsPage() {
  const toast = useToast()
  const [dashboards, setDashboards] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [aiPrompt, setAiPrompt] = useState('')
  const [generating, setGenerating] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await getDashboards()
      setDashboards(data.dashboards || data || [])
    } catch { toast.error('Failed to load dashboards') }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await createDashboard(newName)
      setNewName('')
      setShowCreate(false)
      toast.success('Dashboard created')
      load()
    } catch { toast.error('Failed to create') }
  }

  const handleDelete = async (id) => {
    try {
      await deleteDashboard(id)
      toast.success('Dashboard deleted')
      load()
    } catch { toast.error('Failed to delete') }
  }

  const handleAiGenerate = async () => {
    if (!aiPrompt.trim()) return
    setGenerating(true)
    try {
      await autoGenerate(aiPrompt)
      setAiPrompt('')
      toast.success('Dashboard generated!')
      load()
    } catch (err) {
      toast.error(err.response?.data?.error || 'AI generation failed')
    }
    setGenerating(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">Dashboards</h1>
            <p className="text-sm text-zinc-500">Create and manage your data dashboards</p>
          </div>
          <Button onClick={() => setShowCreate(true)} size="sm">
            <Plus className="w-4 h-4" /> New Dashboard
          </Button>
        </div>

        {/* AI Generate */}
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Wand2 className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-zinc-200">AI Dashboard Generator</span>
          </div>
          <div className="flex gap-2">
            <input
              value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAiGenerate()}
              placeholder="Describe the dashboard you want... e.g. 'Customer spending analysis'"
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-purple-500/30"
            />
            <Button onClick={handleAiGenerate} loading={generating} size="sm" className="bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700">
              <Sparkles className="w-4 h-4" /> Generate
            </Button>
          </div>
          <div className="flex gap-2 mt-2">
            {['Revenue overview', 'Top customers', 'Sales by category'].map(q => (
              <button key={q} onClick={() => setAiPrompt(q)} className="px-2 py-1 rounded-md text-[10px] bg-white/5 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer">{q}</button>
            ))}
          </div>
        </div>

        {loading ? <LoadingSpinner text="Loading dashboards..." /> :
          dashboards.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="No dashboards yet"
              description="Create your first dashboard manually or let AI generate one for you."
            />
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {dashboards.map(d => (
                <div key={d.id} className="glass rounded-xl p-5 hover:border-white/15 transition-all group">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-zinc-100 text-sm">{d.name}</h3>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {d.widgets?.length || 0} widgets
                      </p>
                    </div>
                    <button onClick={() => handleDelete(d.id)} className="p-1 opacity-0 group-hover:opacity-100 hover:bg-rose-500/10 rounded transition-all cursor-pointer">
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    {(d.widgets || []).slice(0, 4).map((w, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-500">{w.chart_type}</span>
                    ))}
                  </div>
                  <Link
                    to={`/dashboards/${d.id}`}
                    className="mt-4 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-white/[0.06] text-xs text-blue-400 hover:from-blue-500/20 hover:to-purple-500/20 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" /> Open Dashboard
                  </Link>
                </div>
              ))}
            </div>
          )}

        {/* Create Modal */}
        <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Dashboard">
          <div className="space-y-4">
            <Input
              label="Dashboard Name"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="My Dashboard"
              autoFocus
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={handleCreate}>Create</Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  )
}
