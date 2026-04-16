import { useState, useEffect, useCallback } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import { useAuth } from '../context/AuthContext'
import { useDb } from '../context/DbContext'
import { useToast } from '../context/ToastContext'
import { getSnapshots, createSnapshot, restoreSnapshot, deleteSnapshot } from '../api/snapshots'
import { History, Plus, RotateCcw, Trash2, Database, Shield } from 'lucide-react'

export default function SnapshotsPage() {
  const { user } = useAuth()
  const { activeDb, dbInfo } = useDb()
  const toast = useToast()
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const isAdmin = user?.role === 'ADMIN'

  const load = useCallback(async () => {
    try {
      const data = await getSnapshots()
      setSnapshots(data.snapshots || data || [])
    } catch { toast.error('Failed to load snapshots') }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    setActing(true)
    try {
      const data = await createSnapshot()
      if (data.success !== false) {
        toast.success('Snapshot created')
        load()
      } else toast.error(data.error || 'Failed to create')
    } catch { toast.error('Failed to create snapshot') }
    setActing(false)
  }

  const handleRestore = async (snapId, connName) => {
    setActing(true)
    try {
      const data = await restoreSnapshot(snapId, connName)
      if (data.success !== false) toast.success('Snapshot restored')
      else toast.error(data.error || 'Restore failed')
    } catch { toast.error('Restore failed') }
    setActing(false)
  }

  const handleDelete = async (snapId) => {
    try {
      await deleteSnapshot(snapId)
      toast.success('Snapshot deleted')
      load()
    } catch { toast.error('Delete failed') }
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
              <History className="w-6 h-6 text-emerald-400" /> Snapshots
            </h1>
            <p className="text-sm text-zinc-500">Backup and restore your databases</p>
          </div>
          {isAdmin && dbInfo?.supports_snapshot && (
            <Button onClick={handleCreate} loading={acting} size="sm">
              <Plus className="w-4 h-4" /> Create Snapshot
            </Button>
          )}
        </div>

        {/* Active DB Info */}
        <div className="glass rounded-xl p-4 flex items-center gap-3">
          <Database className="w-5 h-5 text-blue-400" />
          <div>
            <span className="text-sm text-zinc-200">{activeDb}</span>
            <span className="text-xs text-zinc-500 ml-2">{dbInfo?.display_type}</span>
          </div>
          {dbInfo?.supports_snapshot ? (
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">Snapshots Supported</span>
          ) : (
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded bg-zinc-500/10 text-zinc-500">Snapshots Not Supported</span>
          )}
        </div>

        {!isAdmin && (
          <div className="glass rounded-xl p-4 border-l-4 border-amber-500 flex items-center gap-2">
            <Shield className="w-4 h-4 text-amber-400" />
            <span className="text-sm text-amber-400">Admin access required to manage snapshots</span>
          </div>
        )}

        {loading ? <LoadingSpinner text="Loading snapshots..." /> :
          snapshots.length === 0 ? (
            <EmptyState icon={History} title="No snapshots" description="Snapshots are created automatically before write operations, or you can create them manually." />
          ) : (
            <div className="overflow-auto rounded-lg border border-white/[0.06]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.06]">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Connection</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Taken At</th>
                    {isAdmin && <th className="px-4 py-3 text-right text-xs font-semibold text-zinc-400">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map(s => (
                    <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="px-4 py-3 text-zinc-300">{s.connection_name}</td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">{s.db_type}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500 font-mono">{s.id}</td>
                      <td className="px-4 py-3 text-xs text-zinc-400">{s.formatted_time || s.timestamp}</td>
                      {isAdmin && (
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="success" size="sm" onClick={() => handleRestore(s.id, s.connection_name)} loading={acting}>
                              <RotateCcw className="w-3 h-3" /> Restore
                            </Button>
                            <Button variant="danger" size="sm" onClick={() => handleDelete(s.id)}>
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
    </AppShell>
  )
}
