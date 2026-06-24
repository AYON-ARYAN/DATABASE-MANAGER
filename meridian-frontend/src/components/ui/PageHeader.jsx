import { cn } from '../../lib/utils'

/**
 * Consistent page header used across every page.
 * icon + title + subtitle on the left, optional actions slot on the right.
 */
export default function PageHeader({ icon: Icon, title, subtitle, badge, actions, className = '' }) {
  return (
    <div className={cn('mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between', className)}>
      <div className="flex items-center gap-4 min-w-0">
        {Icon && (
          <div className="relative shrink-0">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 blur-md opacity-50" />
            <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 shadow-lg">
              <Icon className="h-6 w-6 text-white" />
            </div>
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-50 truncate">{title}</h1>
            {badge}
          </div>
          {subtitle && <p className="mt-0.5 text-sm text-zinc-400 truncate">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
