import { useState, useRef, useEffect } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Input, { Textarea } from '../components/ui/Input'
import ResultsTable from '../components/data/ResultsTable'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { GradientCard } from '../components/ui/Card'
import { useAuth } from '../context/AuthContext'
import { useDb } from '../context/DbContext'
import { useToast } from '../context/ToastContext'
import {
  deepAsk, executeRaw, autoInsights, dataHealth,
  fetchKpis, fetchAnomalies,
} from '../api/commandCenter'
import ReactMarkdown from 'react-markdown'
import {
  Rocket, Sparkles, Send, Terminal, AlertTriangle, FileText,
  Download, Play, Zap, TrendingUp, Activity, Target,
  CheckCircle2, XCircle, ShieldCheck, Wand2, Gauge,
} from 'lucide-react'

const TABS = [
  { id: 'deep', label: 'Deep Ask', icon: Sparkles, desc: 'AI Q&A with full DB context' },
  { id: 'execute', label: 'Execute Anything', icon: Terminal, desc: 'Raw SQL power console (ADMIN)' },
  { id: 'insights', label: 'Auto-Insights', icon: Wand2, desc: 'Surprise me — parallel AI findings' },
  { id: 'kpis', label: 'Business KPIs', icon: Target, desc: 'Auto-extracted KPIs' },
  { id: 'health', label: 'Data Health', icon: ShieldCheck, desc: 'Quality scan across all tables' },
  { id: 'anomalies', label: 'Anomalies', icon: Activity, desc: '3-sigma outlier detection' },
  { id: 'report', label: 'Smart PPT', icon: FileText, desc: 'Generate full PPT report' },
]

export default function CommandCenterPage() {
  const { user } = useAuth()
  const { activeDb, dbInfo } = useDb()
  const toast = useToast()
  const [tab, setTab] = useState('deep')

  return (
    <AppShell wide>
      <div className="space-y-6 animate-fade-up">
        {/* Hero */}
        <div className="relative overflow-hidden rounded-2xl p-6 bg-gradient-to-br from-blue-600/20 via-purple-600/20 to-pink-600/20 border border-white/10">
          <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/20 rounded-full blur-3xl -translate-y-24 translate-x-24" />
          <div className="relative flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Rocket className="w-6 h-6 text-purple-400" />
                <h1 className="text-2xl font-bold text-zinc-100">Command Center</h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase tracking-wider font-bold">
                  AI Suite
                </span>
              </div>
              <p className="text-sm text-zinc-400">
                Brand-grade intelligence across <span className="text-zinc-200 font-medium">{activeDb}</span>
                {dbInfo && <span className="text-zinc-500"> · {dbInfo.display_type}</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] px-2 py-1 rounded-md bg-white/5 border border-white/10 text-zinc-400">
                Logged in as <span className="text-zinc-200 font-medium">{user?.username}</span>
              </span>
              <span className="text-[11px] px-2 py-1 rounded-md bg-gradient-to-r from-blue-500 to-purple-600 text-white font-bold">
                {user?.role}
              </span>
            </div>
          </div>
        </div>

        {/* Tab strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`group p-3 rounded-xl border text-left transition-all cursor-pointer ${
                tab === t.id
                  ? 'bg-gradient-to-br from-blue-500/15 to-purple-500/15 border-purple-500/40 shadow-lg shadow-purple-500/10'
                  : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.05]'
              }`}
            >
              <t.icon className={`w-4 h-4 mb-2 ${tab === t.id ? 'text-purple-400' : 'text-zinc-500 group-hover:text-zinc-300'}`} />
              <div className={`text-xs font-semibold ${tab === t.id ? 'text-white' : 'text-zinc-300'}`}>
                {t.label}
              </div>
              <div className="text-[10px] text-zinc-600 mt-0.5 leading-tight">{t.desc}</div>
            </button>
          ))}
        </div>

        {/* Panels */}
        {tab === 'deep' && <DeepAskPanel toast={toast} />}
        {tab === 'execute' && <ExecuteAnythingPanel toast={toast} role={user?.role} />}
        {tab === 'insights' && <AutoInsightsPanel toast={toast} />}
        {tab === 'kpis' && <KpiPanel toast={toast} />}
        {tab === 'health' && <DataHealthPanel toast={toast} />}
        {tab === 'anomalies' && <AnomaliesPanel toast={toast} />}
        {tab === 'report' && <SmartPptPanel toast={toast} />}
      </div>
    </AppShell>
  )
}

/* -------------------- DEEP ASK -------------------- */
function DeepAskPanel({ toast }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  const suggested = [
    'What is this database about in one paragraph?',
    'Top 5 most important tables and why',
    'Are there any data quality problems I should know?',
    'Write me a revenue trend query',
    'What relationships exist between customers and orders?',
  ]

  const ask = async (q) => {
    const query = q ?? question
    if (!query.trim()) return
    setLoading(true)
    try {
      const data = await deepAsk(query, true, history.slice(-4))
      if (data.error) { toast.error(data.error); setLoading(false); return }
      setAnswer(data)
      setHistory(prev => [...prev, { user: query, assistant: data.answer || '' }].slice(-10))
      setQuestion('')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Deep Ask failed')
    }
    setLoading(false)
  }

  const exportAnswerPpt = async () => {
    if (!answer) return
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = '/api/command-center/answer-ppt'
    form.target = '_blank'
    const payload = {
      question: history[history.length - 1]?.user || 'Question',
      answer_markdown: answer.answer || '',
      sql: answer.executed?.sql || '',
      columns: answer.executed?.columns || [],
      rows: answer.executed?.rows || [],
    }
    for (const [k, v] of Object.entries(payload)) {
      const input = document.createElement('input')
      input.type = 'hidden'
      input.name = k
      input.value = typeof v === 'string' ? v : JSON.stringify(v)
      form.appendChild(input)
    }
    // Use fetch for JSON body instead; actually open in new tab via blob
    try {
      const res = await fetch('/api/command-center/answer-ppt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      })
      if (!res.ok) { toast.error('PPT export failed'); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `deep_ask_${Date.now()}.pptx`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('PPT downloaded')
    } catch { toast.error('PPT export failed') }
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1.5">
              Ask anything about the entire database
            </label>
            <textarea
              ref={inputRef}
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }}
              placeholder="e.g. Which products drove the most revenue last year and why?"
              rows={2}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-purple-500/40 resize-none"
            />
          </div>
          <Button onClick={() => ask()} loading={loading} className="flex-shrink-0">
            <Send className="w-4 h-4" /> Deep Ask
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {suggested.map(s => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="px-2.5 py-1 rounded-md text-[11px] bg-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-white/10 transition-colors cursor-pointer border border-white/[0.06]"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingSpinner text="Consulting the database brain..." />}

      {answer && !loading && (
        <div className="space-y-4 animate-fade-up">
          <div className="glass rounded-xl p-5 border-l-4 border-purple-500">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-zinc-200">AI Answer</span>
              </div>
              <button
                onClick={exportAnswerPpt}
                className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/30 text-xs text-purple-300 hover:bg-purple-500/20 transition-colors cursor-pointer"
              >
                <Download className="w-3 h-3" /> Export PPT
              </button>
            </div>
            <div className="markdown-body">
              <ReactMarkdown>{answer.answer || 'No answer generated.'}</ReactMarkdown>
            </div>

            {answer.suggested_queries?.length > 0 && (
              <div className="mt-4 pt-3 border-t border-white/[0.06]">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Suggested follow-ups</div>
                <div className="flex flex-wrap gap-2">
                  {answer.suggested_queries.map((q, i) => (
                    <button key={i} onClick={() => ask(q)}
                      className="px-2 py-1 rounded-md text-[10px] bg-blue-500/10 border border-blue-500/20 text-blue-300 hover:bg-blue-500/20 transition-colors cursor-pointer">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {answer.executed && (
            <div className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-medium text-zinc-300">Auto-executed SQL</span>
              </div>
              <pre className="text-xs text-purple-300 font-mono bg-black/30 rounded p-2 overflow-x-auto mb-3">{answer.executed.sql}</pre>
              {answer.executed.error ? (
                <p className="text-xs text-rose-400">{answer.executed.error}</p>
              ) : answer.executed.columns?.length > 0 ? (
                <ResultsTable columns={answer.executed.columns} rows={answer.executed.rows || []} maxHeight="300px" />
              ) : (
                <p className="text-xs text-zinc-500">No rows returned.</p>
              )}
            </div>
          )}
        </div>
      )}

      {history.length > 0 && !loading && (
        <div className="glass rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2 px-1">Conversation</div>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {history.map((h, i) => (
              <div key={i} className="text-xs p-2 rounded-lg bg-white/[0.02]">
                <div className="text-zinc-300"><span className="text-purple-400 font-semibold">You:</span> {h.user}</div>
                <div className="text-zinc-500 mt-1 line-clamp-2"><span className="text-blue-400 font-semibold">AI:</span> {h.assistant.slice(0, 200)}{h.assistant.length > 200 ? '…' : ''}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* -------------------- EXECUTE ANYTHING -------------------- */
function ExecuteAnythingPanel({ toast, role }) {
  const [sql, setSql] = useState('')
  const [snap, setSnap] = useState(true)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [confirmDanger, setConfirmDanger] = useState(false)

  const isAdmin = role === 'ADMIN'
  const lower = sql.trim().toLowerCase()
  const isDangerous = /\b(drop|truncate|delete|alter|update|insert|create)\b/.test(lower)

  const run = async () => {
    if (!sql.trim()) return
    if (isDangerous && !confirmDanger) {
      toast.warning('Destructive SQL detected — click Execute again to confirm.')
      setConfirmDanger(true)
      return
    }
    setLoading(true)
    setConfirmDanger(false)
    try {
      const data = await executeRaw(sql, snap)
      if (data.error) toast.error(data.error)
      else {
        setResults(data)
        toast.success(`Executed ${data.statements?.length || 0} statement(s) in ${data.elapsed_ms}ms`)
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Execution failed')
    }
    setLoading(false)
  }

  if (!isAdmin) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <ShieldCheck className="w-12 h-12 text-amber-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-zinc-200 mb-2">Admin Access Required</h3>
        <p className="text-sm text-zinc-400">The Execute Anything console lets you run any SQL (DDL, DML, DCL) against the entire database. Only administrators can access it.</p>
      </div>
    )
  }

  const templates = [
    { label: 'Table schema', sql: 'SELECT name, sql FROM sqlite_master WHERE type = \'table\'' },
    { label: 'Row counts', sql: 'SELECT name FROM sqlite_master WHERE type=\'table\'' },
    { label: 'List indexes', sql: 'SELECT name, tbl_name FROM sqlite_master WHERE type=\'index\'' },
    { label: 'Analyze DB', sql: 'ANALYZE' },
    { label: 'Vacuum', sql: 'VACUUM' },
  ]

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium text-zinc-200">SQL Power Console</span>
            {isDangerous && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 uppercase tracking-wider font-bold">
                Destructive
              </span>
            )}
          </div>
          <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
            <input type="checkbox" checked={snap} onChange={e => setSnap(e.target.checked)} />
            Auto-snapshot before writes
          </label>
        </div>
        <textarea
          value={sql}
          onChange={e => { setSql(e.target.value); setConfirmDanger(false) }}
          placeholder="-- Run any SQL against the whole database&#10;-- Multiple statements supported (separate with ;)&#10;SELECT * FROM ..."
          rows={8}
          className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-emerald-300 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/40 resize-y"
        />
        <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
          <div className="flex gap-1.5 flex-wrap">
            {templates.map(tp => (
              <button key={tp.label} onClick={() => setSql(tp.sql)}
                className="px-2 py-1 rounded-md text-[10px] bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 transition-colors cursor-pointer border border-white/[0.06]">
                {tp.label}
              </button>
            ))}
          </div>
          <Button onClick={run} loading={loading}
            variant={isDangerous ? 'danger' : 'primary'}>
            <Play className="w-4 h-4" /> {confirmDanger ? 'Confirm Execute' : 'Execute'}
          </Button>
        </div>
      </div>

      {results && (
        <div className="space-y-3 animate-fade-up">
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>{results.statements?.length || 0} statement(s)</span>
            <span>·</span>
            <span>{results.elapsed_ms}ms</span>
            {results.snapshot_taken && <><span>·</span><span className="text-emerald-400">Snapshot saved</span></>}
          </div>
          {results.statements?.map((s, i) => (
            <div key={i} className="glass rounded-xl p-4">
              <pre className="text-[11px] text-purple-300 font-mono bg-black/30 rounded p-2 overflow-x-auto mb-2">{s.sql}</pre>
              {s.error ? (
                <div className="flex items-start gap-2 p-2 rounded bg-rose-500/10 border border-rose-500/20">
                  <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-rose-300">{s.error}</p>
                </div>
              ) : s.columns?.length > 0 ? (
                <>
                  <div className="text-[10px] text-zinc-500 mb-2">{s.row_count} row(s)</div>
                  <ResultsTable columns={s.columns} rows={s.rows} maxHeight="300px" />
                </>
              ) : (
                <div className="flex items-center gap-2 text-xs text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Executed. No rows returned.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* -------------------- AUTO-INSIGHTS -------------------- */
function AutoInsightsPanel({ toast }) {
  const [count, setCount] = useState(6)
  const [focus, setFocus] = useState('')
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const data = await autoInsights(count, focus)
      if (data.error) toast.error(data.error)
      else setInsights(data)
    } catch { toast.error('Auto-insights failed') }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4">
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <Input label="Focus (optional)" value={focus} onChange={e => setFocus(e.target.value)}
              placeholder="e.g. focus on customer behavior" />
          </div>
          <div className="w-24">
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Count</label>
            <input type="number" min={3} max={10} value={count}
              onChange={e => setCount(Number(e.target.value))}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-blue-500/30" />
          </div>
          <Button onClick={run} loading={loading}
            className="bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700">
            <Wand2 className="w-4 h-4" /> Surprise Me
          </Button>
        </div>
      </div>

      {loading && <LoadingSpinner text="AI is exploring your data..." />}

      {insights && !loading && (
        <div className="grid md:grid-cols-2 gap-4 animate-fade-up">
          {insights.insights?.map((ins, i) => (
            <div key={i} className="glass rounded-xl p-4">
              <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                {ins.title}
              </h3>
              {ins.rationale && <p className="text-xs text-zinc-500 mb-2">{ins.rationale}</p>}
              <pre className="text-[10px] text-purple-300 font-mono bg-black/30 rounded p-2 overflow-x-auto mb-2">{ins.sql}</pre>
              {ins.error ? (
                <p className="text-xs text-rose-400">{ins.error}</p>
              ) : ins.columns?.length > 0 ? (
                <ResultsTable columns={ins.columns} rows={ins.rows} maxHeight="200px" />
              ) : (
                <p className="text-xs text-zinc-500">No rows returned.</p>
              )}
            </div>
          )) || <p className="text-sm text-zinc-500 col-span-2 text-center py-8">No insights generated.</p>}
        </div>
      )}
    </div>
  )
}

/* -------------------- KPIs -------------------- */
function KpiPanel({ toast }) {
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const data = await fetchKpis()
      if (data.error) toast.error(data.error)
      else setKpis(data)
    } catch { toast.error('KPI extraction failed') }
    setLoading(false)
  }

  const gradients = [
    'from-blue-600 to-indigo-600',
    'from-purple-600 to-pink-600',
    'from-emerald-600 to-teal-600',
    'from-orange-600 to-rose-600',
    'from-cyan-600 to-blue-600',
    'from-pink-600 to-violet-600',
    'from-amber-600 to-orange-600',
    'from-teal-600 to-emerald-600',
  ]

  const formatValue = (v) => {
    if (v == null) return '—'
    if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    return String(v)
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-400" /> AI-Extracted Business KPIs
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">The AI reads your schema and writes the KPI queries it thinks matter most.</p>
        </div>
        <Button onClick={run} loading={loading}>
          <Gauge className="w-4 h-4" /> Extract KPIs
        </Button>
      </div>

      {loading && <LoadingSpinner text="Finding what matters..." />}

      {kpis && !loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-fade-up">
          {kpis.kpis?.map((k, i) => (
            <div key={i} className={`rounded-xl p-4 bg-gradient-to-br text-white relative overflow-hidden ${gradients[i % gradients.length]}`}>
              <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full -translate-y-6 translate-x-6" />
              <div className="relative">
                <div className="text-xs font-medium opacity-80">{k.label}</div>
                <div className="text-2xl font-bold mt-1">
                  {k.error ? <span className="text-rose-200 text-sm">Failed</span> : formatValue(k.value)}
                </div>
                {k.rationale && <div className="text-[10px] opacity-60 mt-1 line-clamp-2">{k.rationale}</div>}
              </div>
            </div>
          )) || <p className="text-sm text-zinc-500 col-span-4 text-center py-8">No KPIs generated.</p>}
        </div>
      )}
    </div>
  )
}

/* -------------------- DATA HEALTH -------------------- */
function DataHealthPanel({ toast }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const data = await dataHealth()
      if (data.error) toast.error(data.error)
      else setReport(data)
    } catch { toast.error('Scan failed') }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> Data Health Scan
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">Checks every table for NULL ratios, duplicates, and empty tables.</p>
        </div>
        <Button onClick={run} loading={loading}>
          <Play className="w-4 h-4" /> Run Scan
        </Button>
      </div>

      {loading && <LoadingSpinner text="Inspecting every table..." />}

      {report && !loading && (
        <div className="space-y-3 animate-fade-up">
          <div className="grid grid-cols-3 gap-3">
            <GradientCard gradient="from-rose-600 to-pink-600" icon={AlertTriangle}
              label="High-NULL warnings" value={report.totals?.null_warnings || 0} />
            <GradientCard gradient="from-amber-600 to-orange-600" icon={AlertTriangle}
              label="Duplicate warnings" value={report.totals?.dup_warnings || 0} />
            <GradientCard gradient="from-zinc-600 to-zinc-700" icon={AlertTriangle}
              label="Empty tables" value={report.totals?.empty_tables || 0} />
          </div>

          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-white/[0.04] border-b border-white/[0.06]">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Table</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Rows</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Issues</th>
                </tr>
              </thead>
              <tbody>
                {report.report?.map((r, i) => (
                  <tr key={i} className="border-b border-white/[0.03]">
                    <td className="px-4 py-2.5 text-zinc-300 font-medium">{r.table}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-500">{r.rows?.toLocaleString() || 0}</td>
                    <td className="px-4 py-2.5">
                      {r.issues?.length === 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Clean
                        </span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {r.issues.map((iss, j) => (
                            <span key={j} className={`text-xs px-2 py-0.5 rounded inline-flex items-center gap-1 w-fit ${
                              iss.kind === 'empty_table' ? 'bg-zinc-500/10 text-zinc-400' :
                              iss.kind === 'high_null' ? 'bg-rose-500/10 text-rose-400' :
                              'bg-amber-500/10 text-amber-400'
                            }`}>
                              <AlertTriangle className="w-3 h-3" /> {iss.msg}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

/* -------------------- ANOMALIES -------------------- */
function AnomaliesPanel({ toast }) {
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const data = await fetchAnomalies()
      if (data.error) toast.error(data.error)
      else setFindings(data)
    } catch { toast.error('Scan failed') }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-rose-400" /> Statistical Anomaly Detection
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">Scans numeric columns for values outside ±3σ bands (up to 5,000 sample rows per column).</p>
        </div>
        <Button onClick={run} loading={loading}>
          <Activity className="w-4 h-4" /> Scan
        </Button>
      </div>

      {loading && <LoadingSpinner text="Crunching statistics..." />}

      {findings && !loading && (
        <div className="space-y-2 animate-fade-up">
          {findings.findings?.length === 0 ? (
            <div className="glass rounded-xl p-8 text-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
              <p className="text-sm text-zinc-300">No anomalies found in numeric columns.</p>
            </div>
          ) : (
            <div className="glass rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.06]">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Table</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Column</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Mean</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Stddev</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Outliers</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Range (±3σ)</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.findings.map((f, i) => (
                    <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="px-4 py-2.5 text-xs text-zinc-300">{f.table}</td>
                      <td className="px-4 py-2.5 text-xs text-zinc-300 font-mono">{f.column}</td>
                      <td className="px-4 py-2.5 text-xs text-zinc-400">{f.mean}</td>
                      <td className="px-4 py-2.5 text-xs text-zinc-400">{f.stddev}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-[11px] px-2 py-0.5 rounded bg-rose-500/10 text-rose-400">
                          {f.outliers_in_sample} / {f.sample_size}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[10px] text-zinc-500 font-mono">
                        [{f.bounds[0]} … {f.bounds[1]}]
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* -------------------- SMART PPT -------------------- */
function SmartPptPanel({ toast }) {
  const [topic, setTopic] = useState('Q4 Intelligence Report')
  const [generating, setGenerating] = useState(false)

  const generate = async () => {
    setGenerating(true)
    try {
      const res = await fetch('/api/command-center/smart-ppt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ topic }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast.error(data.error || 'PPT generation failed')
        setGenerating(false)
        return
      }
      const ctype = res.headers.get('content-type') || ''
      if (ctype.includes('application/json')) {
        const data = await res.json()
        toast.error(data.error || 'PPT generation failed')
        setGenerating(false)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${topic.replace(/\W+/g, '_')}_${Date.now()}.pptx`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('PPT ready!')
    } catch { toast.error('PPT generation failed') }
    setGenerating(false)
  }

  return (
    <div className="space-y-4">
      <div className="glass-bright rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-pink-500/20 to-purple-500/20 border border-pink-500/30 flex items-center justify-center flex-shrink-0">
            <FileText className="w-7 h-7 text-pink-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-semibold text-zinc-100">Smart PowerPoint Generator</h3>
            <p className="text-sm text-zinc-400 mt-1">
              The AI generates 6 analytical queries, executes them, writes commentary, builds charts, and packages everything into a 16:9 presentation — all in one click.
            </p>
            <ul className="text-xs text-zinc-500 mt-3 space-y-1">
              <li>• Title slide with branded subtitle</li>
              <li>• Executive summary (AI-written, markdown)</li>
              <li>• Schema & relationships slide</li>
              <li>• One insight slide per analytical query (narrative + chart)</li>
              <li>• Raw data tables for traceability</li>
            </ul>
          </div>
        </div>

        <div className="mt-5 flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <Input label="Report Title / Topic" value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Customer Cohort Deep Dive" />
          </div>
          <Button onClick={generate} loading={generating}
            className="bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700">
            <Download className="w-4 h-4" /> Generate PPT
          </Button>
        </div>
        {generating && <p className="text-xs text-zinc-500 mt-3">This may take 20–60 seconds as the AI runs multiple analyses...</p>}
      </div>
    </div>
  )
}
