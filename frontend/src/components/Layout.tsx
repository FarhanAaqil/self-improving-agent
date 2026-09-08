import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  BarChart3,
  History,
  PlayCircle,
  ShieldCheck,
  Terminal,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { getHealth } from '../api/client'

const NAV_ITEMS = [
  { to: '/', label: 'New Run', icon: PlayCircle },
  { to: '/history', label: 'Run History', icon: History },
  { to: '/eval', label: 'Evaluation', icon: BarChart3 },
  { to: '/security', label: 'Security & Threat Model', icon: ShieldCheck },
]

export default function Layout() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  })

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/60 flex flex-col justify-between p-4 select-none">
        <div className="space-y-6">
          <Link to="/" className="flex items-center gap-2.5 px-2 py-1 group">
            <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20 group-hover:bg-indigo-500 transition-colors">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <div className="font-semibold text-sm leading-tight text-slate-100">Self-Improving</div>
              <div className="text-xs text-slate-400">Code Agent</div>
            </div>
          </Link>

          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                    }`
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* System telemetry footer */}
        <div className="border-t border-slate-800/80 pt-4 px-2 space-y-2 text-xs">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-emerald-400" />
              API Status
            </span>
            <span className="font-mono text-emerald-400 font-medium">
              {health?.status === 'healthy' ? 'online' : 'checking...'}
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-400">
            <span>Docker Sandbox</span>
            <span
              className={`font-mono px-1.5 py-0.5 rounded text-[10px] ${
                health?.docker_available
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
              }`}
            >
              {health?.docker_available ? 'active' : 'subprocess fallback'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-slate-800 bg-slate-900/30 backdrop-blur px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-sm text-slate-400 font-mono">
            <span>agent</span>
            <span>/</span>
            <span className="text-slate-200 font-sans">workspace</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono border border-slate-700/60">
              v1.0.0
            </span>
          </div>
        </header>

        {/* Demo Mode Banner */}
        {health?.demo_mode && (
          <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2 text-xs text-amber-300 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <span className="inline-block px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200 font-mono font-bold uppercase text-[10px]">
                Demo Mode
              </span>
              <span>This is a sandbox demonstration instance, not hardened production infrastructure.</span>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
