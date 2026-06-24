import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../context/AuthContext'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Zap } from 'lucide-react'

export default function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      if (data.success) {
        navigate('/')
      } else {
        setError(data.error || 'Invalid credentials')
      }
    } catch {
      setError('Login failed. Is the server running?')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated ambient background */}
      <div className="aurora-bg" aria-hidden="true" />

      <div className="relative z-10 gradient-ring glass-vibrant rounded-3xl p-8 w-full max-w-sm animate-fade-up shadow-2xl shadow-black/50">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative mb-4">
            <div className="absolute inset-0 rounded-2xl bg-animated-gradient blur-lg opacity-60" />
            <div className="relative w-14 h-14 rounded-2xl bg-animated-gradient flex items-center justify-center shadow-lg shadow-purple-500/40">
              <Zap className="w-7 h-7 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold gradient-text">Meridian Data</h1>
          <p className="text-sm text-zinc-500 mt-1">AI-Powered Database Explorer</p>
        </div>

        {error && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="Username"
            name="username"
            id="username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Enter username"
            autoComplete="username"
            autoFocus
          />
          <Input
            label="Password"
            name="password"
            id="password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Enter password"
            autoComplete="current-password"
          />
          <Button type="submit" loading={loading} className="w-full mt-2">
            Sign In
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-white/[0.06]">
          <p className="text-xs text-zinc-500 text-center mb-3">Demo Credentials</p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { user: 'viewer1', pass: 'viewer123', role: 'Viewer', color: 'from-emerald-500 to-teal-500' },
              { user: 'editor1', pass: 'editor123', role: 'Editor', color: 'from-blue-500 to-cyan-500' },
              { user: 'admin1', pass: 'admin123', role: 'Admin', color: 'from-purple-500 to-pink-500' },
            ].map(cred => (
              <button
                key={cred.user}
                type="button"
                onClick={() => { setUsername(cred.user); setPassword(cred.pass) }}
                className="text-center p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-colors cursor-pointer"
              >
                <div className={`text-[10px] font-bold bg-gradient-to-r ${cred.color} bg-clip-text text-transparent`}>
                  {cred.role}
                </div>
                <div className="text-[10px] text-zinc-500 mt-0.5">{cred.user}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
