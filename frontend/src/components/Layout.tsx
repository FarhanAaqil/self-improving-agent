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
  { to: '/eval', label: 'Eval Dashboard', icon: BarChart3 },
  { to: '/security', label: 'Security & Threat Model', icon: ShieldCheck },
]

export default function Layout() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  })

  return (
    <div className="flex h-screen bg-canvas text-ink overflow-hidden font-sans">
      {/* Left Rail */}
      <aside className="w-64 border-r border-border bg-surface flex flex-col justify-between p-4 select-none shrink-0">
        <div className="space-y-6">
          <Link to="/" className="flex items-center gap-2.5 px-2 py-1 group">
            <div className="h-8 w-8 rounded bg-accent flex items-center justify-center text-white font-bold transition-colors">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <div className="font-semibold text-sm leading-tight text-ink">Self-Improving</div>
              <div className="text-xs text-ink-secondary">Code Agent</div>
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
                    `flex items-center gap-3 px-3 py-2 rounded text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-accent-subtle text-accent border border-accent/20'
                        : 'text-ink-secondary hover:text-ink hover:bg-canvas'
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

        {/* System telemetry footer in left rail */}
        <div className="border-t border-border pt-4 px-2 space-y-2 text-xs">
          <div className="flex items-center justify-between text-ink-secondary">
            <span className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-status-success" />
              API Status
            </span>
            <span className="font-mono text-status-success font-medium">
              {health?.status === 'healthy' ? 'online' : 'checking...'}
            </span>
          </div>
          <div className="flex items-center justify-between text-ink-secondary">
            <span>Docker Sandbox</span>
            <span
              className={`font-mono px-1.5 py-0.5 rounded text-[10px] ${
                health?.docker_available
                  ? 'bg-status-success-subtle text-status-success border border-status-success/30'
                  : 'bg-status-warning-subtle text-status-warning border border-status-warning/30'
              }`}
            >
              {health?.docker_available ? 'active' : 'subprocess fallback'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Plane */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-canvas">
        <header className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs text-ink-secondary">
            <span className="font-mono">agent</span>
            <span>/</span>
            <span className="text-ink font-medium">workspace</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs px-2 py-0.5 rounded bg-surface-sunken text-ink-secondary font-mono border border-border">
              v1.0.0
            </span>
          </div>
        </header>

        {/* Demo Mode Banner */}
        {health?.demo_mode && (
          <div className="bg-status-warning-subtle border-b border-status-warning/20 px-6 py-2 text-xs text-status-warning flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <span className="inline-block px-1.5 py-0.5 rounded bg-status-warning text-white font-mono font-bold uppercase text-[10px]">
                Demo Mode
              </span>
              <span>This is a sandbox demonstration instance, not hardened production infrastructure.</span>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="max-w-[1000px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
