import { createContext, useContext, useState, useCallback, useMemo } from 'react'

const ToastContext = createContext(null)

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info') => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const toast = useMemo(() => ({
    success: (msg) => addToast(msg, 'success'),
    error: (msg) => addToast(msg, 'error'),
    warning: (msg) => addToast(msg, 'warning'),
    info: (msg) => addToast(msg, 'info'),
  }), [addToast])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`animate-fade-up px-4 py-3 rounded-lg text-sm font-medium shadow-lg backdrop-blur-xl border max-w-sm
              ${t.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : ''}
              ${t.type === 'error' ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' : ''}
              ${t.type === 'warning' ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' : ''}
              ${t.type === 'info' ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : ''}
            `}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
