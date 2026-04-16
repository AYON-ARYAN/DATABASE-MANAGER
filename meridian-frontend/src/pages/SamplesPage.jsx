import { useState, useEffect, useCallback, useMemo } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useToast } from '../context/ToastContext'
import { useDb } from '../context/DbContext'
import { listSamples, installSample } from '../api/samples'
import {
  Package, Download, CheckCircle2, Database, Cloud, Cpu,
  Sparkles, Filter, Search, ExternalLink, Zap,
} from 'lucide-react'

const KIND_LABELS = {
  download: { label: 'Real-World', icon: Download, color: 'blue' },
  synthetic: { label: 'Synthetic', icon: Cpu, color: 'purple' },
  remote: { label: 'Remote Template', icon: Cloud, color: 'amber' },
}

const KIND_COLORS = {
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  purple: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

const GRADIENTS = [
  'from-blue-600/20 to-indigo-600/20',
  'from-purple-600/20 to-pink-600/20',
  'from-emerald-600/20 to-teal-600/20',
  'from-orange-600/20 to-rose-600/20',
  'from-cyan-600/20 to-blue-600/20',
  'from-pink-600/20 to-violet-600/20',
  'from-amber-600/20 to-orange-600/20',
  'from-teal-600/20 to-emerald-600/20',
]

export default function SamplesPage() {
  const toast = useToast()
  const { refreshConnections } = useDb()
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState({})
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const [kind, setKind] = useState('All')

  const load = useCallback(async () => {
    try {
      const data = await listSamples()
      setSamples(data.samples || [])
    } catch { toast.error('Failed to load samples') }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const categories = useMemo(() => {
    const s = new Set(samples.map(s => s.category).filter(Boolean))
    return ['All', ...Array.from(s).sort()]
  }, [samples])

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase()
    return samples.filter(s => {
      if (cat !== 'All' && s.category !== cat) return false
      if (kind !== 'All' && s.kind !== kind) return false
      if (!term) return true
      return (
        s.name.toLowerCase().includes(term) ||
        s.description.toLowerCase().includes(term) ||
        (s.tags || []).some(t => t.toLowerCase().includes(term))
      )
    })
  }, [samples, q, cat, kind])

  const handleInstall = async (s) => {
    if (s.kind === 'remote') {
      // Copy template to clipboard & guide
      try {
        await navigator.clipboard.writeText(JSON.stringify(s.template, null, 2))
        toast.success('Template copied! Paste into the Databases > Add Connection form.')
      } catch { toast.info('Use the template from the card.') }
      return
    }
    setInstalling(p => ({ ...p, [s.id]: true }))
    try {
      const res = await installSample(s.id)
      if (res.success) {
        toast.success(res.message || 'Installed')
        await refreshConnections()
        await load()
      } else {
        toast.error(res.message || 'Install failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Install failed')
    }
    setInstalling(p => ({ ...p, [s.id]: false }))
  }

  const installedCount = samples.filter(s => s.installed).length
  const downloadable = samples.filter(s => s.kind === 'download').length
  const synthetic = samples.filter(s => s.kind === 'synthetic').length
  const remote = samples.filter(s => s.kind === 'remote').length

  return (
    <AppShell wide>
      <div className="space-y-6 animate-fade-up">
        {/* Hero */}
        <div className="relative overflow-hidden rounded-2xl p-6 bg-gradient-to-br from-emerald-600/20 via-blue-600/20 to-purple-600/20 border border-white/10">
          <div className="absolute top-0 right-0 w-72 h-72 bg-blue-500/20 rounded-full blur-3xl -translate-y-28 translate-x-28" />
          <div className="relative flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Package className="w-6 h-6 text-emerald-400" />
                <h1 className="text-2xl font-bold text-zinc-100">Sample Databases</h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wider font-bold">
                  Test Bed
                </span>
              </div>
              <p className="text-sm text-zinc-400">
                {samples.length} databases across {categories.length - 1} categories — install any with one click.
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <StatPill label="Real-World" count={downloadable} icon={Download} color="text-blue-400" />
              <StatPill label="Synthetic" count={synthetic} icon={Cpu} color="text-purple-400" />
              <StatPill label="Remote" count={remote} icon={Cloud} color="text-amber-400" />
              <StatPill label="Installed" count={installedCount} icon={CheckCircle2} color="text-emerald-400" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="glass rounded-xl p-3 flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Search samples..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500/40"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <select value={cat} onChange={e => setCat(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none cursor-pointer">
              {categories.map(c => <option key={c} value={c} className="bg-zinc-900">{c}</option>)}
            </select>
            <select value={kind} onChange={e => setKind(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none cursor-pointer">
              <option value="All" className="bg-zinc-900">All kinds</option>
              <option value="download" className="bg-zinc-900">Real-World</option>
              <option value="synthetic" className="bg-zinc-900">Synthetic</option>
              <option value="remote" className="bg-zinc-900">Remote Template</option>
            </select>
          </div>
        </div>

        {loading && <LoadingSpinner text="Loading sample catalog..." />}

        {!loading && (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((s, i) => (
              <SampleCard
                key={s.id}
                sample={s}
                gradient={GRADIENTS[i % GRADIENTS.length]}
                installing={!!installing[s.id]}
                onInstall={() => handleInstall(s)}
              />
            ))}
            {filtered.length === 0 && (
              <div className="col-span-full text-center py-16">
                <Package className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
                <p className="text-zinc-400">No samples match your filters.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}

function StatPill({ label, count, icon: Icon, color }) {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/5 border border-white/10">
      <Icon className={`w-3 h-3 ${color}`} />
      <span className="text-[11px] text-zinc-400">{label}</span>
      <span className="text-[11px] text-zinc-200 font-semibold">{count}</span>
    </div>
  )
}

function SampleCard({ sample, gradient, installing, onInstall }) {
  const k = KIND_LABELS[sample.kind] || KIND_LABELS.synthetic
  const KIcon = k.icon
  return (
    <div className={`relative rounded-xl p-5 bg-gradient-to-br ${gradient} border border-white/[0.08] hover:border-white/20 transition-all group overflow-hidden`}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full blur-2xl -translate-y-12 translate-x-12" />
      <div className="relative">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-white/10 border border-white/10 flex items-center justify-center flex-shrink-0">
              <Database className="w-5 h-5 text-zinc-100" />
            </div>
            <div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border inline-flex items-center gap-1 uppercase tracking-wider font-bold ${KIND_COLORS[k.color]}`}>
                <KIcon className="w-3 h-3" /> {k.label}
              </span>
              <div className="text-[10px] text-zinc-500 mt-1">{sample.category}</div>
            </div>
          </div>
          {sample.installed && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 inline-flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Installed
            </span>
          )}
        </div>

        <h3 className="text-base font-semibold text-zinc-100 mb-1">{sample.name}</h3>
        <p className="text-xs text-zinc-400 mb-3 line-clamp-3">{sample.description}</p>

        <div className="flex items-center gap-3 text-[10px] text-zinc-500 mb-3">
          <span className="inline-flex items-center gap-1"><Database className="w-3 h-3" />{sample.db_type}</span>
          <span>·</span>
          <span>{sample.tables} tables</span>
          <span>·</span>
          <span>{sample.size}</span>
        </div>

        <div className="flex flex-wrap gap-1 mb-4">
          {(sample.tags || []).slice(0, 4).map(t => (
            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-400 border border-white/[0.06]">
              {t}
            </span>
          ))}
        </div>

        {sample.kind === 'remote' && sample.template && (
          <pre className="text-[10px] text-emerald-300 font-mono bg-black/40 rounded p-2 mb-3 overflow-x-auto max-h-24">
{JSON.stringify(sample.template, null, 2)}
          </pre>
        )}

        <Button
          onClick={onInstall}
          loading={installing}
          variant={sample.installed ? 'secondary' : 'primary'}
          size="sm"
          className="w-full"
        >
          {sample.kind === 'remote' ? (
            <><ExternalLink className="w-3.5 h-3.5" /> Copy Template</>
          ) : sample.installed ? (
            <><Zap className="w-3.5 h-3.5" /> Reinstall</>
          ) : (
            <><Sparkles className="w-3.5 h-3.5" /> Install</>
          )}
        </Button>
      </div>
    </div>
  )
}
