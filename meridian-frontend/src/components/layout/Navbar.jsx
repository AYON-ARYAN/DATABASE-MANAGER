import { Link, useLocation } from 'react-router'
import { useAuth } from '../../context/AuthContext'
import { useDb } from '../../context/DbContext'
import { NAV_ITEMS } from '../../lib/constants'
import {
  Terminal, LayoutDashboard, BarChart3, BrainCircuit,
  Database, History, Settings, LogOut, Menu, X, Zap, Rocket, Package
} from 'lucide-react'
import { useState } from 'react'

const iconMap = { Terminal, LayoutDashboard, BarChart3, BrainCircuit, Database, History, Settings, Rocket, Package }

export default function Navbar() {
  const { user, logout } = useAuth()
  const { activeDb, dbInfo } = useDb()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const roleColors = {
    ADMIN: 'from-purple-500 to-pink-500',
    EDITOR: 'from-blue-500 to-cyan-500',
    VIEWER: 'from-emerald-500 to-teal-500',
  }

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-40 h-14 bg-zinc-950/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="h-full max-w-[1600px] mx-auto px-4 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-zinc-100 hidden sm:block">Meridian Data</span>
          </Link>

          {/* Nav Links - Desktop */}
          <div className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map(item => {
              const Icon = iconMap[item.icon]
              const active = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
                    ${active
                      ? 'bg-white/10 text-white'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
                    }`}
                >
                  {Icon && <Icon className="w-3.5 h-3.5" />}
                  {item.label}
                </Link>
              )
            })}
          </div>

          {/* Right section */}
          <div className="flex items-center gap-3">
            {dbInfo && (
              <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/5 border border-white/5">
                <Database className="w-3 h-3 text-blue-400" />
                <span className="text-xs text-zinc-300">{activeDb}</span>
                <span className="text-[10px] text-zinc-500 bg-white/5 px-1.5 py-0.5 rounded">
                  {dbInfo.display_type}
                </span>
              </div>
            )}

            {user && (
              <div className="flex items-center gap-2">
                <div className={`px-2 py-0.5 rounded-md text-[10px] font-bold bg-gradient-to-r ${roleColors[user.role]} text-white`}>
                  {user.role}
                </div>
                <span className="text-xs text-zinc-400 hidden sm:block">{user.username}</span>
                <button
                  onClick={logout}
                  className="p-1.5 hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
                  title="Logout"
                >
                  <LogOut className="w-3.5 h-3.5 text-zinc-400" />
                </button>
              </div>
            )}

            {/* Mobile menu button */}
            <button
              className="md:hidden p-1.5 hover:bg-white/5 rounded-lg cursor-pointer"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X className="w-5 h-5 text-zinc-300" /> : <Menu className="w-5 h-5 text-zinc-300" />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile Nav */}
      {mobileOpen && (
        <div className="fixed inset-0 z-30 pt-14 bg-zinc-950/95 backdrop-blur-xl md:hidden">
          <div className="flex flex-col p-4 gap-1">
            {NAV_ITEMS.map(item => {
              const Icon = iconMap[item.icon]
              const active = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all
                    ${active ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/5'}`}
                >
                  {Icon && <Icon className="w-5 h-5" />}
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </>
  )
}
