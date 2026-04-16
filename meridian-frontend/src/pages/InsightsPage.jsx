import { useState } from 'react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useToast } from '../context/ToastContext'
import { generateInsights } from '../api/analysis'
import ReactMarkdown from 'react-markdown'
import { Lightbulb, Sparkles } from 'lucide-react'

export default function InsightsPage() {
  const toast = useToast()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const data = await generateInsights()
      if (data.error) toast.error(data.error)
      else setResult(data)
    } catch { toast.error('Failed to generate insights') }
    setLoading(false)
  }

  return (
    <AppShell>
      <div className="space-y-6 animate-fade-up">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Lightbulb className="w-6 h-6 text-amber-400" /> Schema Insights
          </h1>
          <p className="text-sm text-zinc-500">AI-powered intelligence about your database structure</p>
        </div>

        {!result && !loading && (
          <div className="glass rounded-xl p-8 text-center">
            <Sparkles className="w-12 h-12 text-purple-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-200 mb-2">Generate Schema Report</h3>
            <p className="text-sm text-zinc-500 mb-6 max-w-md mx-auto">
              AI will analyze your database schema, relationships, and structure to produce a comprehensive intelligence report.
            </p>
            <Button onClick={handleGenerate} size="lg">
              <Sparkles className="w-5 h-5" /> Generate Report
            </Button>
          </div>
        )}

        {loading && <LoadingSpinner text="Generating insights..." />}

        {result && (
          <div className="glass rounded-xl p-6 border-l-4 border-purple-500">
            <div className="markdown-body">
              <ReactMarkdown>{result.report || result.summary || JSON.stringify(result)}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
