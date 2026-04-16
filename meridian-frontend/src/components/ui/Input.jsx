import { cn } from '../../lib/utils'

export default function Input({ className = '', label, ...props }) {
  return (
    <div>
      {label && <label className="block text-xs font-medium text-zinc-400 mb-1.5">{label}</label>}
      <input
        className={cn(
          'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100',
          'placeholder:text-zinc-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20',
          'transition-colors duration-200',
          className
        )}
        {...props}
      />
    </div>
  )
}

export function Textarea({ className = '', label, ...props }) {
  return (
    <div>
      {label && <label className="block text-xs font-medium text-zinc-400 mb-1.5">{label}</label>}
      <textarea
        className={cn(
          'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100',
          'placeholder:text-zinc-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20',
          'transition-colors duration-200 resize-none',
          className
        )}
        {...props}
      />
    </div>
  )
}

export function Select({ className = '', label, options = [], ...props }) {
  return (
    <div>
      {label && <label className="block text-xs font-medium text-zinc-400 mb-1.5">{label}</label>}
      <select
        className={cn(
          'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100',
          'focus:outline-none focus:border-blue-500/50 cursor-pointer',
          className
        )}
        {...props}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value} className="bg-zinc-900">
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
