import { useState, useEffect } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Textarea } from '../components/ui/Input'
import ChartWrapper from '../components/charts/ChartWrapper'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { GradientCard } from '../components/ui/Card'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { getAdminData, updateLlmConfig, pullOllamaModel, testLlm } from '../api/admin'
import { Settings, Activity, Cpu, Terminal, BarChart3, Zap, Download } from 'lucide-react'

const TABS = [
  { id: 'metrics', label: 'Metrics', icon: BarChart3 },
  { id: 'providers', label: 'Providers', icon: Cpu },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'console', label: 'Console', icon: Terminal },
]

export default function AdminPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [tab, setTab] = useState('metrics')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  // Provider form
  const [groqKey, setGroqKey] = useState('')
  const [groqModel, setGroqModel] = useState('llama-3.3-70b-versatile')
  const [ollamaModel, setOllamaModel] = useState('')
  const [pullName, setPullName] = useState('')
  const [pulling, setPulling] = useState(false)

  // Console
  const [testPrompt, setTestPrompt] = useState('')
  const [testProvider, setTestProvider] = useState('mistral')
  const [testResult, setTestResult] = useState('')
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    getAdminData()
      .then(d => {
        setData(d)
        if (d.llm_config?.providers?.groq) {
          setGroqKey(d.llm_config.providers.groq.api_key || '')
          setGroqModel(d.llm_config.providers.groq.model || 'llama-3.3-70b-versatile')
        }
        if (d.llm_config?.providers?.mistral) {
          setOllamaModel(d.llm_config.providers.mistral.model || 'mistral')
        }
      })
      .catch(() => toast.error('Failed to load admin data'))
      .finally(() => setLoading(false))
  }, [toast])

  if (user?.role !== 'ADMIN') {
    return <AppShell><p className="text-rose-400 py-8 text-center">Admin access required</p></AppShell>
  }

  const summary = data?.summary || {}
  const trends = summary.trends || {}

  const handleSaveConfig = async () => {
    try {
      await updateLlmConfig({
        providers: {
          groq: { api_key: groqKey, model: groqModel },
          mistral: { model: ollamaModel },
        }
      })
      toast.success('Config saved')
    } catch { toast.error('Save failed') }
  }

  const handlePull = async () => {
    if (!pullName.trim()) return
    setPulling(true)
    try {
      const d = await pullOllamaModel(pullName)
      if (d.success) toast.success(`Pulled ${pullName}`)
      else toast.error('Pull failed')
    } catch { toast.error('Pull failed') }
    setPulling(false)
  }

  const handleTest = async () => {
    if (!testPrompt.trim()) return
    setTesting(true)
    try {
      const d = await testLlm(testPrompt, testProvider)
      setTestResult(d.output || JSON.stringify(d, null, 2))
    } catch { setTestResult('Test failed') }
    setTesting(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Settings className="w-6 h-6 text-zinc-400" /> Admin Panel
          </h1>
          <p className="text-sm text-zinc-500">LLM configuration, metrics, and testing</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white/[0.02] rounded-lg p-1 border border-white/[0.06]">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer
                ${tab === t.id ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-zinc-300'}`}
            >
              <t.icon className="w-3.5 h-3.5" /> {t.label}
            </button>
          ))}
        </div>

        {loading ? <LoadingSpinner text="Loading..." /> : (
          <>
            {/* Metrics Tab */}
            {tab === 'metrics' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <GradientCard gradient="from-blue-600 to-indigo-600" icon={Zap} label="Total Calls" value={summary.total_calls || 0} />
                  <GradientCard gradient="from-purple-600 to-pink-600" icon={Activity} label="Avg Latency" value={`${(summary.avg_latency || 0).toFixed(1)}s`} />
                  <GradientCard gradient="from-emerald-600 to-teal-600" icon={Cpu} label="Total Tokens" value={(summary.total_tokens || 0).toLocaleString()} />
                  <GradientCard gradient="from-orange-600 to-rose-600" icon={BarChart3} label="Providers" value={Object.keys(summary.calls_by_provider || {}).length} />
                </div>

                {summary.calls_by_provider && (
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="glass rounded-xl p-5">
                      <h3 className="text-sm font-semibold text-zinc-200 mb-3">Provider Distribution</h3>
                      <ChartWrapper
                        type="doughnut"
                        labels={Object.keys(summary.calls_by_provider)}
                        data={Object.values(summary.calls_by_provider)}
                        height={200}
                      />
                    </div>
                    {trends.labels && (
                      <div className="glass rounded-xl p-5">
                        <h3 className="text-sm font-semibold text-zinc-200 mb-3">Token Usage Trend</h3>
                        <ChartWrapper
                          type="line"
                          labels={trends.labels || []}
                          data={trends.groq_tokens || trends.mistral_tokens || []}
                          height={200}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Providers Tab */}
            {tab === 'providers' && (
              <div className="space-y-4">
                <div className="glass rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-4">Groq (Cloud API)</h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <Input label="API Key" type="password" value={groqKey} onChange={e => setGroqKey(e.target.value)} placeholder="gsk_..." />
                    <Input label="Model" value={groqModel} onChange={e => setGroqModel(e.target.value)} />
                  </div>
                </div>

                <div className="glass rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-zinc-200 mb-4">Ollama (Local)</h3>
                  <Input label="Active Model" value={ollamaModel} onChange={e => setOllamaModel(e.target.value)} placeholder="mistral" />

                  {data?.ollama_models?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {data.ollama_models.map(m => (
                        <button
                          key={m}
                          onClick={() => setOllamaModel(m)}
                          className={`px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer ${
                            ollamaModel === m
                              ? 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
                              : 'bg-white/5 border border-white/[0.06] text-zinc-400 hover:bg-white/10'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-2 mt-4">
                    <Input value={pullName} onChange={e => setPullName(e.target.value)} placeholder="Model name to pull..." className="flex-1" />
                    <Button variant="secondary" onClick={handlePull} loading={pulling}>
                      <Download className="w-4 h-4" /> Pull
                    </Button>
                  </div>
                </div>

                <Button onClick={handleSaveConfig}>Save Configuration</Button>
              </div>
            )}

            {/* Activity Tab */}
            {tab === 'activity' && (
              <div className="glass rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-white/[0.04] border-b border-white/[0.06]">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Time</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Provider</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Model</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Latency</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-400">Tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(summary.recent_history || []).map((h, i) => (
                      <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                        <td className="px-4 py-2.5 text-xs text-zinc-500">{h.timestamp || '-'}</td>
                        <td className="px-4 py-2.5">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">{h.provider}</span>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-zinc-400">{h.model}</td>
                        <td className="px-4 py-2.5 text-xs text-zinc-400">{h.latency ? `${h.latency.toFixed(2)}s` : '-'}</td>
                        <td className="px-4 py-2.5 text-xs text-zinc-400">{h.total_tokens || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Console Tab */}
            {tab === 'console' && (
              <div className="space-y-4">
                <div className="glass rounded-xl p-5">
                  <div className="flex gap-4 mb-4">
                    <select
                      value={testProvider}
                      onChange={e => setTestProvider(e.target.value)}
                      className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none cursor-pointer"
                    >
                      <option value="mistral" className="bg-zinc-900">Mistral (Local)</option>
                      <option value="groq" className="bg-zinc-900">Groq (Cloud)</option>
                    </select>
                  </div>
                  <Textarea value={testPrompt} onChange={e => setTestPrompt(e.target.value)} placeholder="Enter test prompt..." rows={3} />
                  <Button onClick={handleTest} loading={testing} className="mt-3">
                    <Terminal className="w-4 h-4" /> Run Test
                  </Button>
                </div>

                {testResult && (
                  <div className="glass rounded-xl p-5">
                    <h3 className="text-xs font-medium text-zinc-400 mb-2">Output</h3>
                    <pre className="text-sm text-emerald-300 font-mono bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                      {testResult}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
