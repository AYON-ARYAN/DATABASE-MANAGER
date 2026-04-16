import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'
import AppShell from '../components/layout/AppShell'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Textarea } from '../components/ui/Input'
import { useToast } from '../context/ToastContext'
import { executeWrite, dryRun, refineQuery } from '../api/query'
import { ShieldAlert, Play, FlaskConical, RotateCcw, Sparkles } from 'lucide-react'

export default function ReviewPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const toast = useToast()
  const initial = location.state || {}

  const [sql, setSql] = useState(initial.sql || '')
  const [explanation, setExplanation] = useState(initial.explanation || '')
  const [task, setTask] = useState(initial.task || 'WRITE')
  const [feedback, setFeedback] = useState('')
  const [dryResult, setDryResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [refining, setRefining] = useState(false)

  const handleExecute = async () => {
    setLoading(true)
    try {
      const data = await executeWrite(sql)
      if (data.success) {
        toast.success(data.message || 'Query executed successfully')
        navigate('/')
      } else {
        toast.error(data.error || 'Execution failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Execution failed')
    }
    setLoading(false)
  }

  const handleDryRun = async () => {
    try {
      const data = await dryRun(sql)
      setDryResult(data)
    } catch (err) {
      toast.error('Dry run failed')
    }
  }

  const handleRefine = async () => {
    if (!feedback.trim()) return
    setRefining(true)
    try {
      const data = await refineQuery(sql, feedback)
      if (data.success) {
        setSql(data.sql)
        setExplanation(data.explanation || explanation)
        setFeedback('')
        toast.success('Query refined')
      } else {
        toast.error(data.error || 'Refinement failed')
      }
    } catch (err) {
      toast.error('Refinement failed')
    }
    setRefining(false)
  }

  useEffect(() => {
    if (!sql) navigate('/', { replace: true })
  }, [sql, navigate])

  if (!sql) return null

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto space-y-6 animate-fade-up">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-6 h-6 text-amber-400" />
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Review Database Changes</h1>
            <p className="text-sm text-zinc-500">This query modifies your database. Review carefully before executing.</p>
          </div>
        </div>

        {/* SQL Card */}
        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Badge type={task} />
            <span className="text-xs text-zinc-500">Generated SQL</span>
          </div>
          <textarea
            value={sql}
            onChange={e => setSql(e.target.value)}
            className="w-full bg-black/30 rounded-lg p-3 text-sm text-purple-300 font-mono border border-white/[0.06] focus:outline-none focus:border-blue-500/30 resize-none"
            rows={6}
          />
        </div>

        {/* Explanation */}
        {explanation && (
          <div className="glass rounded-xl p-4 border-l-4 border-blue-500">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-zinc-200">AI Logic Explanation</span>
            </div>
            <p className="text-sm text-zinc-400">{explanation}</p>
          </div>
        )}

        {/* Refine */}
        <div className="glass rounded-xl p-4">
          <h3 className="text-sm font-medium text-zinc-300 mb-2">Refine Query</h3>
          <div className="flex gap-2">
            <Textarea
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              placeholder="Describe changes... e.g. 'Add WHERE clause for active users only'"
              rows={2}
              className="flex-1"
            />
            <Button variant="secondary" onClick={handleRefine} loading={refining} className="self-end">
              Refine
            </Button>
          </div>
        </div>

        {/* Dry Run Result */}
        {dryResult && (
          <div className={`glass rounded-xl p-4 border-l-4 ${dryResult.success ? 'border-emerald-500' : 'border-rose-500'}`}>
            <p className="text-sm text-zinc-300">{dryResult.status || (dryResult.success ? 'Dry run passed' : 'Dry run failed')}</p>
            {dryResult.affected_rows != null && (
              <p className="text-xs text-zinc-500 mt-1">Affected rows: {dryResult.affected_rows}</p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Button onClick={handleExecute} loading={loading}>
            <Play className="w-4 h-4" /> Execute
          </Button>
          <Button variant="secondary" onClick={handleDryRun}>
            <FlaskConical className="w-4 h-4" /> Dry Run
          </Button>
          <Button variant="ghost" onClick={() => navigate('/')}>
            <RotateCcw className="w-4 h-4" /> Cancel
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
