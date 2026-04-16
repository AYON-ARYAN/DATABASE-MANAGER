export const ROLES = { VIEWER: 'VIEWER', EDITOR: 'EDITOR', ADMIN: 'ADMIN' }

export const ROLE_PERMISSIONS = {
  VIEWER: new Set(['READ', 'SYSTEM']),
  EDITOR: new Set(['READ', 'WRITE', 'SYSTEM']),
  ADMIN: new Set(['READ', 'WRITE', 'SCHEMA', 'SYSTEM']),
}

export const TASK_COLORS = {
  READ: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
  WRITE: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
  SCHEMA: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30' },
  SYSTEM: { bg: 'bg-zinc-500/10', text: 'text-zinc-400', border: 'border-zinc-500/30' },
  UNKNOWN: { bg: 'bg-zinc-500/10', text: 'text-zinc-400', border: 'border-zinc-500/30' },
}

export const CHART_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b',
  '#22c55e', '#06b6d4', '#f43f5e', '#a855f7',
  '#14b8a6', '#fb923c',
]

export const GRADIENT_CARDS = [
  'from-blue-600 to-indigo-600',
  'from-purple-600 to-pink-600',
  'from-emerald-600 to-teal-600',
  'from-orange-600 to-rose-600',
  'from-cyan-600 to-blue-600',
  'from-pink-600 to-violet-600',
]

export const PAGE_SIZE = 50

export const NAV_ITEMS = [
  { path: '/', label: 'Query', icon: 'Terminal' },
  { path: '/command-center', label: 'Command Center', icon: 'Rocket' },
  { path: '/overview', label: 'Overview', icon: 'LayoutDashboard' },
  { path: '/dashboards', label: 'Dashboards', icon: 'BarChart3' },
  { path: '/analysis', label: 'Analysis', icon: 'BrainCircuit' },
  { path: '/databases', label: 'Databases', icon: 'Database' },
  { path: '/samples', label: 'Samples', icon: 'Package' },
  { path: '/snapshots', label: 'Snapshots', icon: 'History' },
  { path: '/admin', label: 'Admin', icon: 'Settings' },
]
