export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/5 flex items-center justify-center mb-4">
          <Icon className="w-7 h-7 text-blue-400" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-zinc-200 mb-1">{title}</h3>
      {description && <p className="text-sm text-zinc-500 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
