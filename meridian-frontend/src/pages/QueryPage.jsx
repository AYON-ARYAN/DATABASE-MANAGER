import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import AppShell from '../components/layout/AppShell'
import ResultsTable from '../components/data/ResultsTable'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { GradientCard } from '../components/ui/Card'
import { useDb } from '../context/DbContext'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { runCommand, paginateResults } from '../api/query'
import { setProvider } from '../api/admin'
import ReactMarkdown from 'react-markdown'
import {
  Send, Terminal, Table2, Key, ListTree, Hash, FileCode,
  ChevronLeft, ChevronRight, Download, FileSpreadsheet,
  Clock, Database, Sparkles
} from 'lucide-react'

export default function QueryPage() {
  const { activeDb, connections, dbInfo, llmProvider, setLlmProvider, switchDb } = useDb()
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const inputRef = useRef(null)

  const [command, setCommand] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!command.trim() || loading) return
    setLoading(true)
    try {
      const data = await runCommand(command)
      setResult(data)
      if (data.needs_review) {
        navigate('/review', { state: data })
      }
      // Add to local history
      setHistory(prev => [{
        query: command,
        sql: data.sql,
        task: data.task,
        status: data.error ? 'ERROR' : 'EXECUTED',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }, ...prev].slice(0, 15))
    } catch (err) {
      toast.error(err.response?.data?.error || 'Command failed')
    }
    setLoading(false)
  }

  const handlePage = async (page) => {
    setLoading(true)
    try {
      const data = await paginateResults(page)
      setResult(data)
    } catch (err) {
      toast.error('Pagination failed')
    }
    setLoading(false)
  }

  const quickCmd = (cmd) => { setCommand(cmd); setTimeout(() => handleSubmitDirect(cmd), 50) }
  const handleSubmitDirect = async (cmd) => {
    setLoading(true)
    try {
      const data = await runCommand(cmd)
      setResult(data)
      setHistory(prev => [{ query: cmd, sql: data.sql, task: data.task, status: 'EXECUTED', time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }, ...prev].slice(0, 15))
    } catch (err) { toast.error('Command failed') }
    setLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
  }

  const handleProviderChange = async (p) => {
    try {
      await setProvider(p)
      setLlmProvider(p)
      toast.success(`Switched to ${p === 'groq' ? 'Groq (Cloud)' : 'Mistral (Local)'}`)
    } catch { toast.error('Failed to switch provider') }
  }

  const handleDbSwitch = async (name) => {
    try {
      await switchDb(name)
      setResult(null)
      toast.success(`Switched to ${name}`)
    } catch { toast.error('Failed to switch database') }
  }

  const totalPages = result?.total_rows ? Math.ceil(result.total_rows / (result.page_size || 50)) : 0
  const currentPage = result?.page || 1

  return (
    <AppShell wide>
      <div className="flex gap-4 h-[calc(100vh-80px)]">
        {/* Sidebar - History */}
        {sidebarOpen && (
          <div className="w-64 flex-shrink-0 hidden lg:flex flex-col">
            <div className="glass rounded-xl p-3 flex-1 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">History</h3>
                <Clock className="w-3 h-3 text-zinc-500" />
              </div>
              <div className="flex-1 overflow-y-auto space-y-1.5">
                {history.length === 0 && (
                  <p className="text-xs text-zinc-600 text-center py-4">No queries yet</p>
                )}
                {history.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => { setCommand(h.query) }}
                    className="w-full text-left p-2 rounded-lg hover:bg-white/5 transition-colors group cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Badge type={h.task}>{h.task}</Badge>
                      <span className="text-[10px] text-zinc-600">{h.time}</span>
                    </div>
                    <p className="text-xs text-zinc-400 truncate group-hover:text-zinc-300">{h.query}</p>
                    {h.sql && <p className="text-[10px] text-zinc-600 truncate mt-0.5 font-mono">{h.sql}</p>}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Main area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Context bar */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <select
              value={activeDb}
              onChange={e => handleDbSwitch(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none cursor-pointer"
            >
              {connections.map(c => (
                <option key={c.name} value={c.name} className="bg-zinc-900">{c.name}</option>
              ))}
            </select>

            {dbInfo && (
              <span className="text-[10px] px-2 py-1 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {dbInfo.display_type}
              </span>
            )}

            <select
              value={llmProvider}
              onChange={e => handleProviderChange(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none cursor-pointer"
            >
              <option value="mistral" className="bg-zinc-900">Mistral (Local)</option>
              <option value="groq" className="bg-zinc-900">Groq (Cloud)</option>
            </select>

            <div className="flex-1" />

            {result?.columns && (
              <div className="flex items-center gap-2">
                <a href="/export" target="_blank" className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 text-xs text-zinc-400 transition-colors">
                  <Download className="w-3 h-3" /> CSV
                </a>
                <a href="/export/ppt" target="_blank" className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 text-xs text-zinc-400 transition-colors">
                  <FileSpreadsheet className="w-3 h-3" /> PPT
                </a>
              </div>
            )}
          </div>

          {/* Results area */}
          <div className="flex-1 overflow-y-auto mb-4">
            {!result && !loading && (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/5 flex items-center justify-center mb-5">
                  <Sparkles className="w-8 h-8 text-blue-400" />
                </div>
                <h2 className="text-lg font-semibold text-zinc-200 mb-1">Ask anything about your data</h2>
                <p className="text-sm text-zinc-500 mb-6 max-w-md text-center">
                  Use natural language or SQL commands. Meridian will generate and execute the right query.
                </p>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-xl">
                  {[
                    { icon: Table2, label: 'Show Tables', cmd: 'show tables', gradient: 'from-blue-600 to-indigo-600' },
                    { icon: Key, label: 'Foreign Keys', cmd: 'show foreign keys', gradient: 'from-purple-600 to-pink-600' },
                    { icon: ListTree, label: 'Indexes', cmd: 'show indexes', gradient: 'from-emerald-600 to-teal-600' },
                    { icon: Hash, label: 'Row Counts', cmd: 'show table counts', gradient: 'from-orange-600 to-rose-600' },
                    { icon: FileCode, label: 'Constraints', cmd: 'show constraints', gradient: 'from-cyan-600 to-blue-600' },
                    { icon: Database, label: 'Overview', cmd: 'describe Artist', gradient: 'from-pink-600 to-violet-600' },
                  ].map(card => (
                    <button
                      key={card.cmd}
                      onClick={() => quickCmd(card.cmd)}
                      className={`p-4 rounded-xl bg-gradient-to-br ${card.gradient} text-white text-left hover:scale-[1.02] transition-transform cursor-pointer relative overflow-hidden`}
                    >
                      <div className="absolute top-0 right-0 w-16 h-16 bg-white/5 rounded-full -translate-y-4 translate-x-4" />
                      <card.icon className="w-5 h-5 mb-2 opacity-80" />
                      <div className="text-sm font-medium">{card.label}</div>
                      <div className="text-xs opacity-60 mt-0.5">{card.cmd}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {loading && (
              <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-10 h-10 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                  <span className="text-sm text-zinc-400">Processing query...</span>
                </div>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-4 animate-fade-up">
                {result.error && (
                  <div className="glass rounded-xl p-4 border-l-4 border-rose-500">
                    <p className="text-sm text-rose-400">{result.error}</p>
                  </div>
                )}

                {/* SQL Card */}
                {result.sql && (
                  <div className="glass rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge type={result.task} />
                      <span className="text-xs text-zinc-500">Generated SQL</span>
                    </div>
                    <pre className="text-sm text-purple-300 font-mono bg-black/30 rounded-lg p-3 overflow-x-auto">
                      {result.sql}
                    </pre>
                    {result.explanation && (
                      <p className="text-xs text-zinc-500 mt-2">{result.explanation}</p>
                    )}
                  </div>
                )}

                {/* AI Response */}
                {result.ai_response && (
                  <div className="glass rounded-xl p-4 border-l-4 border-purple-500">
                    <div className="flex items-center gap-2 mb-3">
                      <Sparkles className="w-4 h-4 text-purple-400" />
                      <span className="text-sm font-medium text-zinc-200">AI Response</span>
                    </div>
                    <div className="markdown-body">
                      <ReactMarkdown>{result.ai_response}</ReactMarkdown>
                    </div>
                    {result.ai_suggestions?.length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {result.ai_suggestions.map((s, i) => (
                          <button
                            key={i}
                            onClick={() => quickCmd(s)}
                            className="px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-xs text-purple-400 hover:bg-purple-500/20 transition-colors cursor-pointer"
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Results Table */}
                {result.columns && result.results?.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-zinc-500">
                        {result.total_rows != null ? `${result.total_rows.toLocaleString()} rows` : `${result.results.length} rows`}
                      </span>
                    </div>
                    <ResultsTable columns={result.columns} rows={result.results} maxHeight="50vh" />

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div className="flex items-center justify-center gap-2 mt-3">
                        <Button
                          variant="ghost" size="sm"
                          disabled={currentPage <= 1}
                          onClick={() => handlePage(currentPage - 1)}
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <span className="text-xs text-zinc-400">
                          Page {currentPage} of {totalPages}
                        </span>
                        <Button
                          variant="ghost" size="sm"
                          disabled={currentPage >= totalPages}
                          onClick={() => handlePage(currentPage + 1)}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Input bar */}
          <div className="glass-bright rounded-xl p-3">
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <textarea
                  ref={inputRef}
                  value={command}
                  onChange={e => setCommand(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your database..."
                  rows={1}
                  className="w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 resize-none focus:outline-none"
                  style={{ minHeight: '24px', maxHeight: '120px' }}
                  onInput={e => { e.target.style.height = 'auto'; e.target.style.height = e.target.scrollHeight + 'px' }}
                />
              </div>
              <Button onClick={handleSubmit} loading={loading} size="sm" className="flex-shrink-0">
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <div className="flex gap-2 mt-2 flex-wrap">
              {['show tables', 'show foreign keys', 'show indexes', 'show table counts'].map(cmd => (
                <button
                  key={cmd}
                  onClick={() => quickCmd(cmd)}
                  className="px-2 py-1 rounded-md text-[10px] bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 transition-colors cursor-pointer"
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
