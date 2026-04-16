import { cn } from '../../lib/utils'

const variants = {
  primary: 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white shadow-lg shadow-blue-500/20',
  secondary: 'bg-white/5 border border-white/10 hover:bg-white/10 text-zinc-300',
  danger: 'bg-rose-500/10 border border-rose-500/30 hover:bg-rose-500/20 text-rose-400',
  ghost: 'hover:bg-white/5 text-zinc-400 hover:text-zinc-200',
  success: 'bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 text-emerald-400',
}

const sizes = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({
  variant = 'primary', size = 'md', className = '',
  children, disabled, loading, ...props
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 cursor-pointer',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  )
}
