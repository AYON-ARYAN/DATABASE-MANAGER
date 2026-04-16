import { cn } from '../../lib/utils'

export default function Card({ className = '', gradient, glow, children, ...props }) {
  return (
    <div
      className={cn(
        'glass rounded-xl p-5',
        gradient && `bg-gradient-to-br ${gradient} border-0`,
        glow && `hover:shadow-lg hover:shadow-${glow}-500/10`,
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function GradientCard({ gradient, icon: Icon, label, value, sub, className = '' }) {
  return (
    <div className={cn(
      'rounded-xl p-5 bg-gradient-to-br text-white relative overflow-hidden',
      gradient,
      className
    )}>
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full -translate-y-6 translate-x-6" />
      <div className="relative">
        {Icon && <Icon className="w-5 h-5 mb-2 opacity-80" />}
        <div className="text-sm font-medium opacity-80">{label}</div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {sub && <div className="text-xs opacity-60 mt-1">{sub}</div>}
      </div>
    </div>
  )
}
