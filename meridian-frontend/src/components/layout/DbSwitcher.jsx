import { useNavigate } from 'react-router'
import { Database, Plus, ChevronDown } from 'lucide-react'
import Dropdown, { DropdownItem } from '../ui/Dropdown'
import { useDb } from '../../context/DbContext'
import { useToast } from '../../context/ToastContext'

/** The single, canonical active-database switcher (lives in the navbar). */
export default function DbSwitcher() {
  const { activeDb, connections, dbInfo, switchDb } = useDb()
  const navigate = useNavigate()
  let toast
  try { toast = useToast() } catch { toast = null }

  const handleSwitch = async (name, close) => {
    close()
    if (name === activeDb) return
    try {
      const res = await switchDb(name)
      if (res?.success === false) toast?.error?.(res.error || 'Failed to switch database')
      else toast?.success?.(`Switched to ${name}`)
    } catch (e) {
      toast?.error?.('Failed to switch database')
    }
  }

  return (
    <Dropdown
      align="right"
      trigger={(open) => (
        <button className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 text-xs transition-all cursor-pointer
          ${open ? 'border-white/20 bg-white/10' : 'border-white/10 bg-white/5 hover:bg-white/10'}`}>
          <Database className="h-3.5 w-3.5 text-blue-400" />
          <span className="max-w-[140px] truncate font-medium text-zinc-200">{activeDb || 'No database'}</span>
          {dbInfo?.display_type && (
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-zinc-400">{dbInfo.display_type}</span>
          )}
          <ChevronDown className={`h-3.5 w-3.5 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      )}
    >
      {(close) => (
        <>
          <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Active database
          </div>
          <div className="max-h-72 overflow-y-auto">
            {connections.length === 0 && (
              <div className="px-3 py-2 text-sm text-zinc-500">No connections</div>
            )}
            {connections.map((c) => {
              const name = typeof c === 'string' ? c : c.name
              const type = typeof c === 'string' ? null : c.db_type
              const isActive = name === activeDb
              return (
                <DropdownItem
                  key={name}
                  icon={Database}
                  label={name}
                  description={type || undefined}
                  active={isActive}
                  onClick={() => handleSwitch(name, close)}
                  className={isActive ? 'ring-1 ring-blue-500/30' : ''}
                />
              )
            })}
          </div>
          <div className="my-1 h-px bg-white/10" />
          <DropdownItem
            icon={Plus}
            label="Add database"
            description="Connect a new source"
            onClick={() => { close(); navigate('/create-database') }}
          />
        </>
      )}
    </Dropdown>
  )
}
