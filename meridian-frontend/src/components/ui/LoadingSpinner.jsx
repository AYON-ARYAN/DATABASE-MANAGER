export default function LoadingSpinner({ size = 'md', text }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <svg className={`animate-spin ${sizes[size]} text-blue-500`} viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {text && <span className="text-sm text-zinc-400">{text}</span>}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`}>&nbsp;</div>
}
