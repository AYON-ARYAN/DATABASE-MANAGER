import { useState } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useToast } from '../context/ToastContext'
import { explainCommand } from '../api/admin'
import { BookOpen, Search, Sparkles } from 'lucide-react'

const COMMANDS = [
  { cmd: 'show tables', task: 'SYSTEM', desc: 'List all tables in the database' },
  { cmd: 'describe <table>', task: 'SYSTEM', desc: 'Show table structure, columns, keys, indexes' },
  { cmd: 'show foreign keys', task: 'SYSTEM', desc: 'List all foreign key relationships' },
  { cmd: 'show indexes', task: 'SYSTEM', desc: 'List all indexes across tables' },
  { cmd: 'show table counts', task: 'SYSTEM', desc: 'Row counts for every table' },
  { cmd: 'show constraints', task: 'SYSTEM', desc: 'All PK, FK, NOT NULL, UNIQUE constraints' },
  { cmd: 'show create table <name>', task: 'SYSTEM', desc: 'DDL statement for a table' },
  { cmd: 'top 10 customers by revenue', task: 'READ', desc: 'AI generates: SELECT with JOIN, GROUP BY, ORDER BY' },
  { cmd: 'add a new product', task: 'WRITE', desc: 'AI generates: INSERT INTO statement (requires review)' },
  { cmd: 'delete inactive users', task: 'WRITE', desc: 'AI generates: DELETE statement (requires review)' },
]

export default function CommandGuidePage() {
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleLookup = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const data = await explainCommand(query)
      setResult(data)
    } catch { toast.error('Lookup failed') }
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up max-w-3xl mx-auto">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-blue-400" /> Command Guide
          </h1>
          <p className="text-sm text-zinc-500">Explore commands and understand what they do</p>
        </div>

        {/* Semantic Lookup */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-200 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" /> Semantic Command Lookup
          </h3>
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLookup()}
              placeholder="Describe what you want to do..."
              className="flex-1"
            />
            <Button onClick={handleLookup} loading={loading} size="sm">
              <Search className="w-4 h-4" /> Analyze
            </Button>
          </div>
        </div>

        {/* Lookup Result */}
        {result && (
          <div className="glass rounded-xl p-5 border-l-4 border-purple-500 animate-fade-up">
            <div className="flex items-center gap-2 mb-3">
              <Badge type={result.task}>{result.task}</Badge>
              <span className="text-xs text-zinc-500">Impact: {result.impact}</span>
              <span className="text-xs text-zinc-500">Permissions: {result.permissions}</span>
            </div>
            <p className="text-sm text-zinc-300 mb-2">{result.summary}</p>
            {result.sql_pattern && (
              <pre className="text-xs text-purple-300 font-mono bg-black/30 rounded-lg p-3 overflow-x-auto">
                {result.sql_pattern}
              </pre>
            )}
          </div>
        )}

        {/* Command Reference */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-200 mb-4">Common Commands</h3>
          <div className="space-y-2">
            {COMMANDS.map((c, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-white/[0.02] transition-colors">
                <Badge type={c.task}>{c.task}</Badge>
                <div className="flex-1">
                  <code className="text-sm text-purple-300">{c.cmd}</code>
                  <p className="text-xs text-zinc-500 mt-0.5">{c.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
