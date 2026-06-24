import { useState, useRef, useEffect, useCallback } from 'react'
import { cn } from '../../lib/utils'

/**
 * Headless dropdown / popover.
 * Presentation-only: caller supplies the trigger and the menu content.
 * Opens on click (and optionally hover), closes on outside-click or Esc.
 *
 * Usage:
 *   <Dropdown trigger={(open) => <button>…</button>} align="left" hover>
 *     {(close) => <menu items, call close() on select/> }
 *   </Dropdown>
 */
export default function Dropdown({ trigger, children, align = 'left', hover = false, menuClassName = '' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const closeTimer = useRef(null)

  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(() => () => clearTimeout(closeTimer.current), [])

  const hoverProps = hover ? {
    onMouseEnter: () => { clearTimeout(closeTimer.current); setOpen(true) },
    onMouseLeave: () => { closeTimer.current = setTimeout(() => setOpen(false), 120) },
  } : {}

  return (
    <div className="relative" ref={ref} {...hoverProps}>
      <div onClick={() => setOpen(o => !o)}>
        {trigger(open)}
      </div>
      {open && (
        <div
          className={cn(
            'absolute top-full mt-2 z-50 min-w-[14rem] animate-pop',
            'glass-vibrant rounded-2xl p-1.5 shadow-2xl shadow-black/50',
            align === 'right' ? 'right-0' : 'left-0',
            menuClassName
          )}
        >
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  )
}

/** A single item inside a Dropdown menu. */
export function DropdownItem({ icon: Icon, label, description, active, onClick, className = '' }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-3 px-3 py-2 rounded-xl text-left transition-all duration-150 cursor-pointer group',
        active ? 'bg-white/10 text-white' : 'text-zinc-300 hover:bg-white/[0.07] hover:text-white',
        className
      )}
    >
      {Icon && (
        <span className={cn(
          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors',
          active ? 'bg-gradient-to-br from-blue-500/30 to-purple-500/30 text-white'
                 : 'bg-white/5 text-zinc-400 group-hover:text-white'
        )}>
          <Icon className="h-4 w-4" />
        </span>
      )}
      <span className="min-w-0">
        <span className="block text-sm font-medium leading-tight">{label}</span>
        {description && <span className="block text-xs text-zinc-500 mt-0.5 leading-snug">{description}</span>}
      </span>
    </button>
  )
}
