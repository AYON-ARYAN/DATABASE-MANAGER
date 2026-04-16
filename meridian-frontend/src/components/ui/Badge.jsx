import { TASK_COLORS } from '../../lib/constants'

export default function Badge({ type, children, className = '' }) {
  const colors = TASK_COLORS[type] || TASK_COLORS.UNKNOWN
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${colors.bg} ${colors.text} ${colors.border} ${className}`}>
      {children || type}
    </span>
  )
}
