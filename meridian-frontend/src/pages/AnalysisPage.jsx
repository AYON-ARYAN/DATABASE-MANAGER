import { useState, useEffect, useRef } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import { Textarea } from '../components/ui/Input'
import ResultsTable from '../components/data/ResultsTable'
import ChartWrapper from '../components/charts/ChartWrapper'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useToast } from '../context/ToastContext'
import { getTablesList, previewTable, analyzeDirect, startFullAnalysis, getAnalysisStatus } from '../api/analysis'
import ReactMarkdown from 'react-markdown'
import { BrainCircuit, Table2, FileCode, Upload, Database, Sparkles, Play } from 'lucide-react'

const TABS = [
  { id: 'table', label: 'From Table', icon: Table2 },
  { id: 'sql', label: 'Custom SQL', icon: FileCode },
  { id: 'csv', label: 'Upload CSV', icon: Upload },
  { id: 'full', label: 'Entire Database', icon: Database },
]

export default function AnalysisPage() {
  const toast = useToast()
  const [tab, setTab] = useState('table')
  const [tables, setTables] = useState([])
  const [selectedTable, setSelectedTable] = useState('')
  const [customSql, setCustomSql] = useState('')
  const [csvFile, setCsvFile] = useState(null)
  const [hint, setHint] = useState('')
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [fullProgress, setFullProgress] = useState(null)
  const fileRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    getTablesList().then(data => setTables(data.tables || [])).catch(() => {})
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const handlePreview = async () => {
    try {
      let data
      if (tab === 'table' && selectedTable) {
        data = await previewTable(selectedTable)
      } else if (tab === 'sql' && customSql) {
        data = await previewTable('custom', customSql)
      }
      setPreview(data)
    } catch { toast.error('Preview failed') }
  }

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setResult(null)
    try {
      let data
      if (tab === 'table') {
        data = await analyzeDirect(selectedTable, '', hint)
      } else if (tab === 'sql') {
        data = await analyzeDirect('custom', customSql, hint)
      } else if (tab === 'csv' && csvFile) {
        const formData = new FormData()
        formData.append('csv_file', csvFile)
        formData.append('hint', hint)
        const res = await fetch('/analyze-csv', { method: 'POST', body: formData, credentials: 'include' })
        data = await res.json()
      }
      if (data?.error) toast.error(data.error)
      else setResult(data)
    } catch (err) { toast.error('Analysis failed') }
    setAnalyzing(false)
  }

  const handleFullAnalysis = async () => {
    setAnalyzing(true)
    setResult(null)
    setFullProgress(null)
    try {
      const { job_id } = await startFullAnalysis()
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const status = await getAnalysisStatus(job_id)
          setFullProgress(status)
          if (status.status === 'complete') {
            clearInterval(pollRef.current)
            pollRef.current = null
            setResult(status.result)
            setAnalyzing(false)
          } else if (status.status === 'error') {
            clearInterval(pollRef.current)
            pollRef.current = null
            toast.error(status.error || 'Analysis failed')
            setAnalyzing(false)
          }
        } catch {
          clearInterval(pollRef.current)
          pollRef.current = null
          toast.error('Status poll failed')
          setAnalyzing(false)
        }
      }, 2000)
    } catch { toast.error('Failed to start analysis'); setAnalyzing(false) }
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-purple-400" /> Data Analysis
          </h1>
          <p className="text-sm text-zinc-500">Analyze your data with AI-powered insights</p>
        </div>

        {/* Source Tabs */}
        <div className="flex gap-1 bg-white/[0.02] rounded-lg p-1 border border-white/[0.06]">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer
                ${tab === t.id ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-zinc-300'}`}
            >
              <t.icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {tab === 'table' && (
          <div className="glass rounded-xl p-4">
            <h3 className="text-sm font-medium text-zinc-300 mb-3">Select a table</h3>
            <div className="grid grid-cols-3 md:grid-cols-4 gap-2 max-h-48 overflow-y-auto">
              {tables.map(t => (
                <button
                  key={t.name}
                  onClick={() => { setSelectedTable(t.name); handlePreview() }}
                  className={`p-2 rounded-lg text-left text-xs transition-all cursor-pointer ${
                    selectedTable === t.name
                      ? 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
                      : 'bg-white/[0.02] border border-white/[0.06] text-zinc-400 hover:bg-white/5'
                  }`}
                >
                  <div className="font-medium truncate">{t.name}</div>
                  <div className="text-[10px] text-zinc-600 mt-0.5">{t.rows} rows</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {tab === 'sql' && (
          <div className="glass rounded-xl p-4">
            <Textarea label="Custom SQL Query" value={customSql} onChange={e => setCustomSql(e.target.value)} placeholder="SELECT * FROM ..." rows={4} />
            <Button variant="secondary" size="sm" onClick={handlePreview} className="mt-2">Preview</Button>
          </div>
        )}

        {tab === 'csv' && (
          <div
            className="glass rounded-xl p-8 text-center border-2 border-dashed border-white/10 cursor-pointer hover:border-blue-500/30 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
            <p className="text-sm text-zinc-400">{csvFile ? csvFile.name : 'Click or drag to upload CSV'}</p>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={e => setCsvFile(e.target.files[0])} />
          </div>
        )}

        {tab === 'full' && (
          <div className="glass rounded-xl p-5 text-center">
            <Database className="w-10 h-10 text-blue-400 mx-auto mb-3" />
            <h3 className="text-sm font-medium text-zinc-200 mb-1">Full Database Analysis</h3>
            <p className="text-xs text-zinc-500 mb-4">AI will analyze the entire database, generate queries, and produce a comprehensive report.</p>
            <Button onClick={handleFullAnalysis} loading={analyzing}>
              <Sparkles className="w-4 h-4" /> Start Full Analysis
            </Button>
          </div>
        )}

        {/* Preview */}
        {preview && !preview.error && (
          <div className="glass rounded-xl p-4">
            <h3 className="text-xs font-medium text-zinc-400 mb-2">Data Preview</h3>
            <ResultsTable columns={preview.columns || []} rows={preview.rows || []} maxHeight="200px" />
          </div>
        )}

        {/* Hint */}
        {tab !== 'full' && (
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Textarea label="Analysis hint (optional)" value={hint} onChange={e => setHint(e.target.value)} placeholder="Focus on trends, outliers, or specific patterns..." rows={2} />
            </div>
            <Button onClick={handleAnalyze} loading={analyzing} disabled={tab === 'table' && !selectedTable} className="self-end">
              <Play className="w-4 h-4" /> Analyze
            </Button>
          </div>
        )}

        {/* Full Analysis Progress */}
        {fullProgress && analyzing && (
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-5 h-5 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
              <span className="text-sm text-zinc-300">{fullProgress.progress || 'Processing...'}</span>
            </div>
            {fullProgress.total_steps > 0 && (
              <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all"
                  style={{ width: `${(fullProgress.step / fullProgress.total_steps) * 100}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4 animate-fade-up">
            {result.summary && (
              <div className="glass rounded-xl p-5 border-l-4 border-purple-500">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-medium text-zinc-200">AI Insights</span>
                </div>
                <div className="markdown-body text-sm">
                  <ReactMarkdown>{result.summary}</ReactMarkdown>
                </div>
              </div>
            )}

            {result.chart && (
              <div className="glass rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-200 mb-3">
                  {result.chart.title || 'Visualization'}
                </h3>
                <ChartWrapper
                  type={result.chart.type || 'bar'}
                  labels={result.chart.labels || []}
                  data={result.chart.data || result.chart.datasets?.[0]?.data || []}
                  height={300}
                />
              </div>
            )}

            {/* Full report insights */}
            {result.insights && result.insights.map((insight, i) => (
              <div key={i} className="glass rounded-xl p-4">
                <h4 className="text-sm font-medium text-zinc-200 mb-2">{insight.title || `Insight ${i + 1}`}</h4>
                {insight.sql && <pre className="text-xs text-purple-300 font-mono bg-black/30 rounded p-2 mb-2 overflow-x-auto">{insight.sql}</pre>}
                <div className="markdown-body text-sm mb-3"><ReactMarkdown>{insight.markdown || insight.finding || ''}</ReactMarkdown></div>
                {insight.chart && (
                  <ChartWrapper
                    type={insight.chart.type || 'bar'}
                    labels={insight.chart.labels || []}
                    data={insight.chart.data || insight.chart.datasets?.[0]?.data || []}
                    height={260}
                  />
                )}
              </div>
            ))}

            {result.executive_summary && (
              <div className="glass rounded-xl p-5 border-l-4 border-blue-500">
                <h3 className="text-sm font-semibold text-zinc-200 mb-2">Executive Summary</h3>
                <div className="markdown-body text-sm">
                  <ReactMarkdown>{result.executive_summary}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
