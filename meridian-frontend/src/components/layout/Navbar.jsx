import { Link, useLocation, useNavigate } from 'react-router'
import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { NAV_GROUPS, NAV_ITEMS } from '../../lib/constants'
import Dropdown, { DropdownItem } from '../ui/Dropdown'
import DbSwitcher from './DbSwitcher'
import {
  Terminal, LayoutDashboard, BarChart3, BrainCircuit, Database, History,
  Settings, LogOut, Menu, X, Zap, Rocket, Package, GitMerge, Lightbulb, ChevronDown,
} from 'lucide-react'

const iconMap = {
  Terminal, LayoutDashboard, BarChart3, BrainCircuit, Database, History,
  Settings, Rocket, Package, GitMerge, Lightbulb,
}

const roleColors = {
  ADMIN: 'from-purple-500 to-pink-500',
  EDITOR: 'from-blue-500 to-cyan-500',
  VIEWER: 'from-emerald-500 to-teal-500',
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const isActive = (path) => location.pathname === path
  const groupActive = (group) =>
    group.kind === 'link' ? isActive(group.path) : group.items.some(i => isActive(i.path))

  return (
    <>
      <nav className="fixed top-0 inset-x-0 z-40 h-14 border-b border-white/[0.06] bg-zinc-950/70 backdrop-blur-xl">
        <div className="mx-auto flex h-full max-w-[1600px] items-center justify-between gap-3 px-4">
          {/* Brand */}
          <Link to="/" className="flex shrink-0 items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-animated-gradient shadow-lg shadow-purple-500/30">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="hidden text-sm font-semibold text-zinc-100 sm:block">Meridian Data</span>
          </Link>

          {/* Desktop nav — grouped dropdowns */}
          <div className="hidden items-center gap-1 md:flex">
            {NAV_GROUPS.map((group) => {
              const active = groupActive(group)
              if (group.kind === 'link') {
                const Icon = iconMap[group.icon]
                return (
                  <Link
                    key={group.label}
                    to={group.path}
                    className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200
                      ${active ? 'bg-white/10 text-white glow-primary' : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-100'}`}
                  >
                    {Icon && <Icon className="h-3.5 w-3.5" />}
                    {group.label}
                  </Link>
                )
              }
              const GroupIcon = iconMap[group.icon]
              return (
                <Dropdown
                  key={group.label}
                  trigger={(open) => (
                    <button
                      className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200 cursor-pointer
                        ${active || open ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-100'}
                        ${active ? 'glow-primary' : ''}`}
                    >
                      {GroupIcon && <GroupIcon className="h-3.5 w-3.5" />}
                      {group.label}
                      <ChevronDown className={`h-3.5 w-3.5 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />
                    </button>
                  )}
                >
                  {(close) => group.items.map((item) => {
                    const ItemIcon = iconMap[item.icon]
                    return (
                      <DropdownItem
                        key={item.path}
                        icon={ItemIcon}
                        label={item.label}
                        description={item.description}
                        active={isActive(item.path)}
                        onClick={() => { close(); navigate(item.path) }}
                      />
                    )
                  })}
                </Dropdown>
              )
            })}
          </div>

          {/* Right cluster */}
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div className="hidden lg:block"><DbSwitcher /></div>

            {user && (
              <Dropdown
                align="right"
                trigger={() => (
                  <button className="flex items-center gap-2 rounded-xl px-1.5 py-1 transition-colors hover:bg-white/5 cursor-pointer">
                    <span className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br text-[10px] font-bold text-white ${roleColors[user.role] || roleColors.VIEWER}`}>
                      {(user.username || '?').slice(0, 1).toUpperCase()}
                    </span>
                    <span className="hidden text-xs font-medium text-zinc-300 sm:block">{user.username}</span>
                    <ChevronDown className="hidden h-3.5 w-3.5 text-zinc-500 sm:block" />
                  </button>
                )}
              >
                {(close) => (
                  <>
                    <div className="px-3 py-2">
                      <div className="text-sm font-semibold text-zinc-100">{user.username}</div>
                      <span className={`mt-1 inline-flex rounded-md bg-gradient-to-r px-2 py-0.5 text-[10px] font-bold text-white ${roleColors[user.role] || roleColors.VIEWER}`}>
                        {user.role}
                      </span>
                    </div>
                    <div className="lg:hidden">
                      <div className="my-1 h-px bg-white/10" />
                      <div className="px-2 py-1"><DbSwitcher /></div>
                    </div>
                    <div className="my-1 h-px bg-white/10" />
                    <DropdownItem icon={Settings} label="Admin" active={isActive('/admin')} onClick={() => { close(); navigate('/admin') }} />
                    <DropdownItem icon={LogOut} label="Log out" onClick={() => { close(); logout() }} className="text-rose-300 hover:text-rose-200" />
                  </>
                )}
              </Dropdown>
            )}

            {/* Mobile menu button */}
            <button
              className="rounded-xl p-1.5 hover:bg-white/5 md:hidden cursor-pointer"
              onClick={() => setMobileOpen(o => !o)}
              aria-label="Menu"
            >
              {mobileOpen ? <X className="h-5 w-5 text-zinc-300" /> : <Menu className="h-5 w-5 text-zinc-300" />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-zinc-950/95 pt-14 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-1 overflow-y-auto p-4">
            <div className="mb-2"><DbSwitcher /></div>
            {NAV_ITEMS.map((item) => {
              const Icon = iconMap[item.icon]
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all
                    ${active ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/5'}`}
                >
                  {Icon && <Icon className="h-5 w-5" />}
                  {item.label}
                </Link>
              )
            })}
            <button
              onClick={() => { setMobileOpen(false); logout() }}
              className="mt-2 flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-rose-300 hover:bg-rose-500/10"
            >
              <LogOut className="h-5 w-5" /> Log out
            </button>
          </div>
        </div>
      )}
    </>
  )
}
