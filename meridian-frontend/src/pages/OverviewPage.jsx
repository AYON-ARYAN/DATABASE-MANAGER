import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import AppShell from '../components/layout/AppShell'
import { GradientCard } from '../components/ui/Card'
import Button from '../components/ui/Button'
import ResultsTable from '../components/data/ResultsTable'
import ChartWrapper from '../components/charts/ChartWrapper'
import Modal from '../components/ui/Modal'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useDb } from '../context/DbContext'
import { useToast } from '../context/ToastContext'
import { getOverview, getErDiagram, runOverviewQuery } from '../api/overview'
import { aiAsk } from '../api/analysis'
import { runCommand, runRawQuery } from '../api/query'
import ReactMarkdown from 'react-markdown'
import mermaid from 'mermaid'

mermaid.initialize({
  theme: 'dark',
  startOnLoad: false,
  securityLevel: 'loose',
  er: { useMaxWidth: true, diagramPadding: 20, layoutDirection: 'TB' },
  themeVariables: { fontSize: '13px' },
})
import {
  LayoutDashboard, Table2, Rows3, Link2, Crown,
  Sparkles, Send, Play, Maximize2, Minimize2,
  Database, RefreshCw, BarChart3, LineChart, PieChart, Donut,
  Activity, Hash, Braces, Download, Wand2, Terminal, FileCode,
  TrendingUp, Layers, Eye,
} from 'lucide-react'

export default function OverviewPage() {
  const { activeDb, dbInfo, connections, switchDb } = useDb()
  const toast = useToast()
  const erRef = useRef(null)

  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erDiagram, setErDiagram] = useState('')
  const [erError, setErError] = useState('')
  const [erLoading, setErLoading] = useState(false)
  const [erFull, setErFull] = useState(false)

  // AI Ask (narrative) — separate from query console
  const [question, setQuestion] = useState('')
  const [askResult, setAskResult] = useState(null)
  const [asking, setAsking] = useState(false)

  // Query Console
  const [queryMode, setQueryMode] = useState('ai') // 'ai' | 'sql'
  const [queryText, setQueryText] = useState('')
  const [queryResult, setQueryResult] = useState(null)
  const [querying, setQuerying] = useState(false)
  const [queryHistory, setQueryHistory] = useState([])
  const [queryModal, setQueryModal] = useState(null)
  const [modalResult, setModalResult] = useState(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getOverview()
      setOverview(data)
    } catch {
      toast.error('Failed to load overview')
    }
    setLoading(false)
  }, [toast])

  useEffect(() => { loadOverview() }, [loadOverview])

  // Load ER diagram
  useEffect(() => {
    let cancelled = false
    const loadEr = async () => {
      setErLoading(true)
      setErError('')
      setErDiagram('')
      try {
        const data = await getErDiagram()
        if (cancelled) return
        if (!data?.success) {
          setErError(data?.error || 'Failed to load ER diagram')
          return
        }
        const tables = data.tables || []
        if (!tables.length) {
          setErError('No tables found in this database.')
          return
        }
        const mmd = buildErMermaid(tables, data.foreign_keys || [])
        if (!mmd) {
          setErError('Could not build a valid ER diagram from the schema.')
          return
        }
        setErDiagram(mmd)
      } catch (e) {
        if (!cancelled) setErError(e?.response?.data?.error || e?.message || 'Failed to load ER diagram')
      } finally {
        if (!cancelled) setErLoading(false)
      }
    }
    loadEr()
    return () => { cancelled = true }
  }, [activeDb])

  // Render Mermaid — waits for the ref to be attached before rendering
  useEffect(() => {
    if (!erDiagram) {
      if (erRef.current) erRef.current.innerHTML = ''
      return
    }
    let cancelled = false

    const waitForRef = async (maxMs = 1500) => {
      const start = performance.now()
      while (!cancelled && !erRef.current && performance.now() - start < maxMs) {
        await new Promise(r => requestAnimationFrame(r))
      }
      return erRef.current
    }

    const renderEr = async () => {
      const target = await waitForRef()
      if (cancelled || !target) return
      try {
        const id = `er-svg-${Date.now()}-${Math.floor(Math.random() * 1e6)}`
        const { svg } = await mermaid.render(id, erDiagram)
        if (cancelled) return
        const el = erRef.current
        if (el) {
          el.innerHTML = svg
          setErError('')
        }
      } catch (e) {
        if (cancelled) return
        const msg = e?.message || String(e) || 'Diagram render failed'
        console.error('[ER] Mermaid render failed:', msg, '\nSource:\n', erDiagram)
        setErError(`Diagram render failed: ${msg.split('\n')[0]}`)
        if (erRef.current) erRef.current.innerHTML = ''
      }
    }
    renderEr()
    return () => { cancelled = true }
  }, [erDiagram])

  const handleAsk = async () => {
    if (!question.trim()) return
    setAsking(true)
    try {
      const data = await aiAsk(question)
      setAskResult(data)
    } catch {
      toast.error('AI Ask failed')
    }
    setAsking(false)
  }

  const handleRunSuggestion = async (query) => {
    setQueryModal(query)
    setModalResult(null)
    try {
      const data = await runOverviewQuery(query)
      setModalResult(data)
    } catch {
      setModalResult({ error: 'Query execution failed' })
    }
  }

  const runQuery = async (textOverride, modeOverride) => {
    const text = (textOverride ?? queryText).trim()
    const mode = modeOverride ?? queryMode
    if (!text) return
    setQuerying(true)
    setQueryResult(null)
    const t0 = performance.now()
    try {
      let data
      if (mode === 'sql') {
        data = await runRawQuery(text, activeDb)
        // Normalise shape
        data = {
          columns: data.columns || data.cols || [],
          results: data.rows || data.results || [],
          sql: text,
          total_rows: (data.rows || data.results || []).length,
          task: 'READ',
        }
      } else {
        data = await runCommand(text)
      }
      const elapsed = Math.round(performance.now() - t0)
      const shaped = {
        ...data,
        columns: data.columns || [],
        rows: data.results || data.rows || [],
        elapsed_ms: elapsed,
        mode,
        text,
      }
      setQueryResult(shaped)
      setQueryHistory(prev => [{ mode, text, ts: Date.now(), rows: shaped.rows.length }, ...prev].slice(0, 8))
      if (data.error) toast.error(data.error)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Query failed')
    }
    setQuerying(false)
  }

  const highlights = overview?.highlights || []

  // Derive top-level KPIs for hero row
  const heroStats = useMemo(() => {
    const h = overview?.highlights || []
    const stats = {}
    for (const item of h) stats[(item.label || '').toLowerCase()] = item.value
    return stats
  }, [overview])

  return (
    <AppShell wide>
      <div className="space-y-6 animate-fade-up">
        {/* =========================== HERO =========================== */}
        <div className="relative overflow-hidden rounded-2xl p-6 bg-gradient-to-br from-blue-600/15 via-indigo-600/15 to-purple-600/15 border border-white/10">
          <div className="absolute top-0 right-0 w-80 h-80 bg-blue-500/15 rounded-full blur-3xl -translate-y-24 translate-x-24 pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/15 rounded-full blur-3xl translate-y-16 -translate-x-16 pointer-events-none" />
          <div className="relative flex items-start justify-between flex-wrap gap-4">
            <div className="flex items-start gap-4 min-w-0">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/30">
                <Database className="w-7 h-7 text-white" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 uppercase tracking-wider font-bold">
                    Active Database
                  </span>
                  {dbInfo && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase tracking-wider font-bold">
                      {dbInfo.display_type}
                    </span>
                  )}
                  {dbInfo?.is_nosql && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wider font-bold">
                      NoSQL
                    </span>
                  )}
                </div>
                <h1 className="text-3xl font-bold text-zinc-100 truncate">{activeDb}</h1>
                <div className="flex items-center gap-4 mt-2 text-xs text-zinc-400 flex-wrap">
                  {heroStats['tables'] != null && (
                    <span className="inline-flex items-center gap-1">
                      <Table2 className="w-3.5 h-3.5 text-blue-400" />
                      <span className="text-zinc-200 font-semibold">{heroStats['tables']}</span> tables
                    </span>
                  )}
                  {heroStats['total rows'] != null && (
                    <span className="inline-flex items-center gap-1">
                      <Rows3 className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-zinc-200 font-semibold">{heroStats['total rows']}</span> rows
                    </span>
                  )}
                  {heroStats['relationships'] != null && (
                    <span className="inline-flex items-center gap-1">
                      <Link2 className="w-3.5 h-3.5 text-purple-400" />
                      <span className="text-zinc-200 font-semibold">{heroStats['relationships']}</span> relationships
                    </span>
                  )}
                  {heroStats['largest table'] && (
                    <span className="inline-flex items-center gap-1">
                      <Crown className="w-3.5 h-3.5 text-amber-400" />
                      largest: <span className="text-zinc-200 font-semibold">{heroStats['largest table']}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={activeDb}
                onChange={e => { switchDb(e.target.value); setQueryResult(null); setAskResult(null); loadOverview() }}
                className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-blue-500/50 cursor-pointer"
              >
                {connections?.map(c => (
                  <option key={c.name} value={c.name} className="bg-zinc-900">{c.name}</option>
                ))}
              </select>
              <Button variant="secondary" size="sm" onClick={loadOverview} loading={loading}>
                <RefreshCw className="w-3.5 h-3.5" /> Refresh
              </Button>
            </div>
          </div>
        </div>

        {/* =========================== QUERY CONSOLE =========================== */}
        <div className="glass-bright rounded-xl p-5">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-semibold text-zinc-100">Query Console</h3>
              <span className="text-[10px] text-zinc-500">Execute against <span className="text-zinc-300 font-medium">{activeDb}</span></span>
            </div>
            <div className="flex items-center gap-1 bg-white/[0.03] rounded-lg p-1 border border-white/[0.06]">
              <button
                onClick={() => setQueryMode('ai')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  queryMode === 'ai' ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" /> Ask AI
              </button>
              <button
                onClick={() => setQueryMode('sql')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  queryMode === 'sql' ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <FileCode className="w-3.5 h-3.5" /> Write SQL
              </button>
            </div>
          </div>

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <textarea
                value={queryText}
                onChange={e => setQueryText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); runQuery() } }}
                placeholder={queryMode === 'ai'
                  ? 'Ask a question in plain English — e.g. "top 10 customers by total spend"'
                  : 'SELECT * FROM customers WHERE country = \'USA\' LIMIT 20'
                }
                rows={queryMode === 'sql' ? 5 : 3}
                className={`w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-500 focus:outline-none focus:border-purple-500/40 resize-y ${
                  queryMode === 'sql' ? 'text-emerald-300 font-mono' : 'text-zinc-100'
                }`}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Button onClick={() => runQuery()} loading={querying} className="flex-shrink-0">
                <Play className="w-4 h-4" /> Run
              </Button>
              <button onClick={() => { setQueryText(''); setQueryResult(null) }}
                className="text-[10px] px-3 py-1 rounded-md bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 transition-colors cursor-pointer border border-white/[0.06]">
                Clear
              </button>
            </div>
          </div>

          {/* Quick prompts */}
          <div className="flex flex-wrap gap-1.5 mt-3">
            {(queryMode === 'ai'
              ? ['show tables', 'top 10 largest tables', 'monthly trend of orders', 'which customers spent the most?', 'any duplicate rows?']
              : ['SELECT name FROM sqlite_master WHERE type=\'table\'', 'PRAGMA table_info(customers)', 'SELECT COUNT(*) FROM orders', 'EXPLAIN QUERY PLAN SELECT 1']
            ).map(q => (
              <button key={q} onClick={() => setQueryText(q)}
                className="px-2 py-1 rounded-md text-[10px] bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 transition-colors cursor-pointer border border-white/[0.06]">
                {q}
              </button>
            ))}
          </div>

          {queryHistory.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/[0.06]">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Recent</div>
              <div className="flex flex-wrap gap-2">
                {queryHistory.map((h, i) => (
                  <button key={i}
                    onClick={() => { setQueryMode(h.mode); setQueryText(h.text); runQuery(h.text, h.mode) }}
                    className="text-[10px] px-2 py-1 rounded-md bg-white/[0.03] border border-white/[0.06] text-zinc-400 hover:bg-white/10 hover:text-zinc-200 transition-colors cursor-pointer max-w-[220px] truncate"
                  >
                    <span className={h.mode === 'sql' ? 'text-emerald-400' : 'text-purple-400'}>{h.mode === 'sql' ? 'SQL' : 'AI'}</span>
                    {' · '}
                    {h.text}
                    {' · '}
                    <span className="text-zinc-600">{h.rows}r</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* =========================== RESULTS =========================== */}
        {querying && <LoadingSpinner text="Executing query..." />}
        {queryResult && !querying && <QueryResultsPanel result={queryResult} toast={toast} />}

        {/* =========================== NARRATIVE AI ASK =========================== */}
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-zinc-200">Narrative AI — ask anything (no execution)</span>
          </div>
          <div className="flex gap-2">
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAsk()}
              placeholder="e.g. What is this database about? How are tables related?"
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-purple-500/30"
            />
            <Button onClick={handleAsk} loading={asking} size="sm">
              <Send className="w-4 h-4" /> Ask
            </Button>
          </div>
          <div className="flex gap-2 mt-2 flex-wrap">
            {['What are the main entities?', 'How are tables related?', 'What insights can you find?'].map(q => (
              <button key={q} onClick={() => setQuestion(q)}
                className="px-2 py-1 rounded-md text-[10px] bg-white/5 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer">
                {q}
              </button>
            ))}
          </div>
          {askResult && (
            <div className="mt-3 border-t border-white/[0.06] pt-3 markdown-body">
              <ReactMarkdown>{askResult.answer || askResult.error || 'No response'}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* =========================== INTEL =========================== */}
        {loading ? <LoadingSpinner text="Loading database intel..." /> : overview && (
          <>
            {/* Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {highlights.map((h, i) => {
                const gradients = ['from-blue-600 to-indigo-600', 'from-purple-600 to-pink-600', 'from-emerald-600 to-teal-600', 'from-orange-600 to-rose-600']
                const icons = [Table2, Rows3, Link2, Crown]
                return (
                  <GradientCard
                    key={i}
                    gradient={gradients[i % gradients.length]}
                    icon={icons[i % icons.length]}
                    label={h.label}
                    value={h.value}
                  />
                )
              })}
            </div>

            {overview.summary && (
              <div className="glass rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-200 mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-400" /> Executive Summary
                </h3>
                <div className="markdown-body text-sm">
                  <ReactMarkdown>{overview.summary}</ReactMarkdown>
                </div>
              </div>
            )}

            <div className="grid md:grid-cols-2 gap-4">
              {overview.table_size_chart && (
                <div className="glass rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-3">Table Sizes</h3>
                  <ChartWrapper
                    type="bar"
                    labels={overview.table_size_chart.labels?.slice(0, 15) || []}
                    data={overview.table_size_chart.data?.slice(0, 15) || []}
                    height={250}
                  />
                </div>
              )}
              {overview.relationship_map?.length > 0 && (
                <div className="glass rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-3">Relationships</h3>
                  <div className="overflow-auto max-h-[250px]">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-zinc-400">
                          <th className="text-left pb-2">From</th>
                          <th className="text-left pb-2">To</th>
                          <th className="text-left pb-2">Via</th>
                        </tr>
                      </thead>
                      <tbody>
                        {overview.relationship_map.map((r, i) => (
                          <tr key={i} className="border-t border-white/[0.03]">
                            <td className="py-1.5 text-blue-400">{r.from}</td>
                            <td className="py-1.5 text-purple-400">{r.to}</td>
                            <td className="py-1.5 text-zinc-400">{r.via}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {overview.suggested_queries?.length > 0 && (
              <div className="glass rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-200 mb-3">Suggested Queries</h3>
                <div className="grid md:grid-cols-2 gap-2">
                  {overview.suggested_queries.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => handleRunSuggestion(q.query || q)}
                      className="text-left p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] hover:bg-white/[0.04] transition-colors cursor-pointer"
                    >
                      <p className="text-xs text-zinc-300">{q.title || q}</p>
                      <p className="text-[10px] text-zinc-600 font-mono mt-1 truncate">{q.query || q}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* =========================== ER DIAGRAM =========================== */}
        <div className="glass rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-zinc-200">ER Diagram</h3>
            <button onClick={() => setErFull(!erFull)} className="p-1 hover:bg-white/10 rounded cursor-pointer">
              {erFull ? <Minimize2 className="w-4 h-4 text-zinc-400" /> : <Maximize2 className="w-4 h-4 text-zinc-400" />}
            </button>
          </div>
          {erLoading && <LoadingSpinner text="Building ER diagram..." />}
          {!erLoading && erError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-sm text-rose-300">
              {erError}
            </div>
          )}
          <div
            ref={erRef}
            style={{ display: erLoading || erError ? 'none' : 'block' }}
            className={`overflow-auto ${erFull ? 'max-h-none' : 'max-h-[500px]'} [&_svg]:max-w-full [&_svg]:h-auto`}
          />
        </div>

        {/* Suggested-Query modal (from intel section) */}
        <Modal open={!!queryModal} onClose={() => setQueryModal(null)} title="Query Result" wide>
          {queryModal && (
            <pre className="text-xs text-purple-300 font-mono bg-black/30 rounded p-2 mb-3 overflow-x-auto">{queryModal}</pre>
          )}
          {!modalResult ? <LoadingSpinner text="Executing..." /> :
            modalResult.error ? <p className="text-sm text-rose-400">{modalResult.error}</p> :
            <ResultsTable columns={modalResult.columns || []} rows={modalResult.rows || []} maxHeight="400px" />
          }
        </Modal>
      </div>
    </AppShell>
  )
}


/* ============================================================
   QueryResultsPanel — inline, multi-view results for console
   ============================================================ */
function QueryResultsPanel({ result, toast }) {
  const { columns = [], rows = [], sql, error, ai_response, task, elapsed_ms, mode, needs_review } = result
  const [view, setView] = useState('table')
  const [chartType, setChartType] = useState(null)

  const profile = useMemo(() => buildProfile(columns, rows), [columns, rows])
  const autoChart = useMemo(() => inferChart(columns, rows, profile), [columns, rows, profile])
  const effectiveType = chartType ?? autoChart?.type

  const chartData = useMemo(() => {
    if (!autoChart) return null
    return {
      labels: autoChart.labels,
      data: autoChart.data,
    }
  }, [autoChart])

  const exportCsv = () => {
    const lines = [columns.join(',')]
    for (const r of rows) lines.push(r.map(v => (v == null ? '' : `"${String(v).replace(/"/g, '""')}"`)).join(','))
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `query_${Date.now()}.csv`; a.click()
    URL.revokeObjectURL(url)
    toast.success('CSV downloaded')
  }

  const exportPpt = async () => {
    try {
      const res = await fetch('/api/command-center/answer-ppt', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: result.text || 'Query',
          answer_markdown: ai_response || '',
          sql: sql || '',
          columns, rows: rows.slice(0, 50),
        }),
      })
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `query_${Date.now()}.pptx`; a.click()
      URL.revokeObjectURL(url)
      toast.success('PPT downloaded')
    } catch { toast.error('PPT export failed') }
  }

  // Scalar result → big KPI
  const isScalar = rows.length === 1 && columns.length === 1
  const scalarValue = isScalar ? rows[0][0] : null

  return (
    <div className="glass rounded-xl p-5 animate-fade-up">
      {/* Header: meta + view toggle + exports */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-bold ${
            mode === 'sql' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
          }`}>
            {mode === 'sql' ? 'SQL' : 'AI'}
          </span>
          {task && <span className="text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-bold bg-blue-500/10 text-blue-400 border border-blue-500/30">{task}</span>}
          <span className="text-xs text-zinc-400 inline-flex items-center gap-1">
            <Rows3 className="w-3 h-3" /> {rows.length.toLocaleString()} rows
          </span>
          <span className="text-xs text-zinc-400 inline-flex items-center gap-1">
            <Activity className="w-3 h-3" /> {elapsed_ms}ms
          </span>
          {needs_review && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 uppercase tracking-wider font-bold">
              Needs review
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={exportCsv}><Download className="w-3 h-3" /> CSV</Button>
          <Button variant="ghost" size="sm" onClick={exportPpt}><Download className="w-3 h-3" /> PPT</Button>
        </div>
      </div>

      {/* Generated SQL */}
      {sql && (
        <div className="mb-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Executed SQL</div>
          <pre className="text-xs text-purple-300 font-mono bg-black/30 rounded p-2 overflow-x-auto">{sql}</pre>
        </div>
      )}

      {/* AI narrative (only in AI mode) */}
      {ai_response && (
        <div className="mb-4 p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-xs font-medium text-zinc-200">AI Response</span>
          </div>
          <div className="markdown-body text-sm">
            <ReactMarkdown>{ai_response}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {/* Scalar KPI view */}
      {!error && isScalar && (
        <div className="rounded-xl p-6 bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-white/10 text-center">
          <div className="text-xs text-zinc-400 uppercase tracking-wider mb-1">{columns[0]}</div>
          <div className="text-5xl font-bold text-zinc-100">
            {typeof scalarValue === 'number' ? scalarValue.toLocaleString() : String(scalarValue ?? '—')}
          </div>
        </div>
      )}

      {/* View toggle */}
      {!error && !isScalar && rows.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-1 bg-white/[0.03] rounded-lg p-1 border border-white/[0.06]">
              <ViewTab active={view === 'table'} icon={Table2} label="Table" onClick={() => setView('table')} />
              <ViewTab active={view === 'chart'} icon={BarChart3} label="Chart" onClick={() => setView('chart')} disabled={!autoChart} />
              <ViewTab active={view === 'stats'} icon={Layers} label="Stats" onClick={() => setView('stats')} />
              <ViewTab active={view === 'json'} icon={Braces} label="JSON" onClick={() => setView('json')} />
            </div>

            {view === 'chart' && autoChart && (
              <div className="flex items-center gap-1 bg-white/[0.03] rounded-lg p-1 border border-white/[0.06]">
                <ChartBtn type="bar" active={effectiveType === 'bar'} onClick={() => setChartType('bar')} />
                <ChartBtn type="line" active={effectiveType === 'line'} onClick={() => setChartType('line')} />
                <ChartBtn type="area" active={effectiveType === 'area'} onClick={() => setChartType('area')} />
                <ChartBtn type="pie" active={effectiveType === 'pie'} onClick={() => setChartType('pie')} />
                <ChartBtn type="doughnut" active={effectiveType === 'doughnut'} onClick={() => setChartType('doughnut')} />
              </div>
            )}
          </div>

          {view === 'table' && <ResultsTable columns={columns} rows={rows} maxHeight="520px" />}

          {view === 'chart' && autoChart && chartData && (
            <div className="p-3 rounded-lg bg-black/20 border border-white/[0.06]">
              <div className="text-xs text-zinc-500 mb-2">
                X: <span className="text-blue-400 font-mono">{autoChart.xCol}</span> · Y: <span className="text-purple-400 font-mono">{autoChart.yCol}</span>
              </div>
              <ChartWrapper type={effectiveType || 'bar'} labels={chartData.labels} data={chartData.data} height={360} />
            </div>
          )}

          {view === 'chart' && !autoChart && (
            <div className="p-8 text-center text-sm text-zinc-500">
              <Eye className="w-8 h-8 mx-auto mb-2 opacity-50" />
              No chartable shape detected. Try a query with a label column + numeric column.
            </div>
          )}

          {view === 'stats' && <StatsView columns={columns} rows={rows} profile={profile} />}

          {view === 'json' && (
            <pre className="text-[10px] text-emerald-300 font-mono bg-black/40 rounded p-3 overflow-auto max-h-[520px] border border-white/[0.06]">
{JSON.stringify({ columns, rows: rows.slice(0, 100) }, null, 2)}
            </pre>
          )}
        </>
      )}

      {!error && !isScalar && rows.length === 0 && (
        <div className="p-8 text-center text-sm text-zinc-500">Query executed — no rows returned.</div>
      )}
    </div>
  )
}

function ViewTab({ active, icon: Icon, label, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
        active ? 'bg-white/10 text-white' : disabled ? 'text-zinc-600 cursor-not-allowed' : 'text-zinc-400 hover:text-zinc-200'
      }`}>
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  )
}

function ChartBtn({ type, active, onClick }) {
  const map = { bar: BarChart3, line: LineChart, area: TrendingUp, pie: PieChart, doughnut: Donut }
  const Icon = map[type] || BarChart3
  return (
    <button onClick={onClick}
      title={type}
      className={`p-1.5 rounded-md transition-all cursor-pointer ${active ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-200'}`}>
      <Icon className="w-3.5 h-3.5" />
    </button>
  )
}

/* ---------- Stats view: per-column profile ---------- */
function StatsView({ columns, rows, profile }) {
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {columns.map((col, i) => {
        const p = profile[i] || {}
        return (
          <div key={i} className="rounded-lg p-3 bg-white/[0.02] border border-white/[0.06]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-zinc-200 font-mono">{col}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                p.type === 'number' ? 'bg-blue-500/10 text-blue-400' :
                p.type === 'date' ? 'bg-purple-500/10 text-purple-400' :
                'bg-zinc-500/10 text-zinc-400'
              }`}>{p.type}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <Stat label="Rows" value={rows.length} />
              <Stat label="Nulls" value={`${p.nulls} (${p.nullPct}%)`} danger={p.nullPct > 30} />
              <Stat label="Unique" value={p.unique} />
              {p.type === 'number' && (
                <>
                  <Stat label="Min" value={p.min} />
                  <Stat label="Max" value={p.max} />
                  <Stat label="Mean" value={p.mean} />
                  <Stat label="Sum" value={p.sum} />
                </>
              )}
              {p.type !== 'number' && p.topValue != null && (
                <Stat label="Most common" value={`${String(p.topValue).slice(0, 24)} (${p.topCount}x)`} span2 />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Stat({ label, value, danger, span2 }) {
  return (
    <div className={`flex items-center justify-between ${span2 ? 'col-span-2' : ''}`}>
      <span className="text-zinc-500">{label}</span>
      <span className={`font-mono ${danger ? 'text-rose-400' : 'text-zinc-200'}`}>{value}</span>
    </div>
  )
}

/* ---------- Helpers: Mermaid ER builder ---------- */
// Mermaid ER grammar is strict: identifiers must start with a letter/underscore,
// contain only alphanumerics/underscore, and every entity needs at least one attribute.
// We also avoid reserved single-word types (PK/FK/UK) colliding with constraint keywords.
const MERMAID_RESERVED = new Set(['PK', 'FK', 'UK'])

function sanitizeIdent(name, fallback = 'col') {
  if (name == null) return fallback
  let s = String(name).replace(/[^A-Za-z0-9_]/g, '_')
  if (!s) return fallback
  if (/^[0-9]/.test(s)) s = '_' + s
  return s
}

function sanitizeType(t) {
  const raw = (t == null ? '' : String(t)).replace(/[^A-Za-z0-9_]/g, '')
  if (!raw) return 'text'
  if (/^[0-9]/.test(raw)) return '_' + raw
  if (MERMAID_RESERVED.has(raw.toUpperCase())) return raw + '_t'
  return raw
}

function buildErMermaid(tables, foreignKeys) {
  if (!Array.isArray(tables) || tables.length === 0) return ''

  const entityNames = new Map() // original -> sanitized, unique
  const used = new Set()
  for (const t of tables) {
    let name = sanitizeIdent(t?.name, 'table')
    let suffix = 1
    while (used.has(name)) name = sanitizeIdent(t?.name, 'table') + '_' + suffix++
    used.add(name)
    entityNames.set(t?.name, name)
  }

  let mmd = 'erDiagram\n'
  for (const t of tables) {
    const entity = entityNames.get(t?.name)
    const cols = Array.isArray(t?.columns) ? t.columns.slice(0, 15) : []
    if (!cols.length) {
      // Mermaid requires an attribute block; give a placeholder so the entity still appears
      mmd += `    ${entity} {\n        text _no_columns\n    }\n`
      continue
    }
    mmd += `    ${entity} {\n`
    const seen = new Set()
    for (const c of cols) {
      let colName = sanitizeIdent(c?.name, 'col')
      let s = 1
      while (seen.has(colName)) colName = sanitizeIdent(c?.name, 'col') + '_' + s++
      seen.add(colName)
      const typ = sanitizeType(c?.type)
      mmd += `        ${typ} ${colName}${c?.pk ? ' PK' : ''}\n`
    }
    mmd += '    }\n'
  }

  for (const fk of (foreignKeys || [])) {
    const from = entityNames.get(fk?.from_table)
    const to = entityNames.get(fk?.to_table)
    if (!from || !to) continue
    const label = String(fk?.from_column || 'fk').replace(/"/g, "'")
    mmd += `    ${from} ||--o{ ${to} : "${label}"\n`
  }
  return mmd
}

/* ---------- Helpers: profiling + chart inference ---------- */
function buildProfile(columns, rows) {
  return columns.map((_, ci) => {
    let nulls = 0
    const vals = []
    for (const r of rows) {
      const v = r[ci]
      if (v == null || v === '') { nulls++; continue }
      vals.push(v)
    }
    const uniques = new Set(vals)
    const nums = vals.map(v => Number(v)).filter(n => !Number.isNaN(n))
    const allNumeric = vals.length > 0 && nums.length === vals.length
    const isDate = !allNumeric && vals.length > 0 && vals.every(v => !Number.isNaN(Date.parse(v)))
    let type = 'string'
    if (allNumeric) type = 'number'
    else if (isDate) type = 'date'

    const result = {
      type,
      nulls,
      nullPct: rows.length ? Math.round((nulls / rows.length) * 100) : 0,
      unique: uniques.size,
    }
    if (type === 'number') {
      const sum = nums.reduce((a, b) => a + b, 0)
      result.sum = round(sum)
      result.mean = round(sum / nums.length)
      result.min = round(Math.min(...nums))
      result.max = round(Math.max(...nums))
    } else {
      const counts = new Map()
      for (const v of vals) counts.set(v, (counts.get(v) || 0) + 1)
      let topValue = null, topCount = 0
      for (const [k, c] of counts) if (c > topCount) { topValue = k; topCount = c }
      result.topValue = topValue
      result.topCount = topCount
    }
    return result
  })
}

function round(n) {
  if (typeof n !== 'number' || !isFinite(n)) return n
  return Math.abs(n) >= 100 ? Math.round(n * 100) / 100 : Math.round(n * 10000) / 10000
}

function inferChart(columns, rows, profile) {
  if (rows.length === 0 || columns.length < 2) return null

  const types = profile.map(p => p.type)
  const numericIdx = types.findIndex(t => t === 'number')
  const labelIdx = types.findIndex((t, i) => i !== numericIdx && t !== 'number')
  const dateIdx = types.findIndex(t => t === 'date')

  // Prefer first non-numeric column as label, fall back to col 0
  const xIdx = dateIdx >= 0 ? dateIdx : (labelIdx >= 0 ? labelIdx : 0)
  const yIdx = numericIdx >= 0 ? numericIdx : (xIdx === 1 ? 0 : 1)
  if (xIdx === yIdx) return null
  if (types[yIdx] !== 'number') return null

  const capped = rows.slice(0, 50)
  const labels = capped.map(r => String(r[xIdx]))
  const data = capped.map(r => Number(r[yIdx]) || 0)

  // Auto pick type: date → line, <=8 categories → pie, else bar
  let type = 'bar'
  if (dateIdx >= 0) type = 'line'
  else if (new Set(labels).size <= 8 && labels.length <= 12) type = 'doughnut'

  return { type, labels, data, xCol: columns[xIdx], yCol: columns[yIdx] }
}
