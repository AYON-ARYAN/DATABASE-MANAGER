import { useEffect } from 'react'
import { X } from 'lucide-react'

export default function Modal({ open, onClose, title, children, wide }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    if (open) document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className={`relative glass-bright animate-fade-up p-6 ${wide ? 'max-w-4xl' : 'max-w-lg'} w-full max-h-[85vh] overflow-y-auto`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-zinc-100">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
