import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  BarChart3,
  History,
  PlayCircle,
  ShieldCheck,
  Terminal,
} from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getHealth, listRuns } from '../api/client'

const NAV_ITEMS = [
  { to: '/', label: 'new run', icon: PlayCircle },
  { to: '/history', label: 'run history', icon: History },
  { to: '/eval', label: 'eval dashboard', icon: BarChart3 },
  { to: '/security', label: 'security & threat model', icon: ShieldCheck },
]

export default function Layout() {
  const location = useLocation()
  const isSecurityPage = location.pathname.startsWith('/security')

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  })

  // Check for any actively running jobs for the persistent run ticker
  const { data: runs = [] } = useQuery({
    queryKey: ['runs-ticker'],
    queryFn: () => listRuns(5),
    refetchInterval: 3000,
  })

  const activeRun = runs.find((r) => r.final_status === 'running')

  return (
    <div className="flex h-screen bg-canvas text-ink overflow-hidden font-sans">
      {/* Left Rail (Nav) */}
      <aside className="w-60 border-r border-border bg-surface flex flex-col justify-between select-none shrink-0 z-10">
        <div className="flex flex-col">
          {/* Logo / Header */}
          <Link
            to="/"
            className="flex items-center gap-3 px-5 py-4 border-b border-border hover:bg-surface-sunken/50 transition-colors"
          >
            <div className="h-7 w-7 bg-accent flex items-center justify-center text-white font-mono font-bold text-xs">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <div className="font-mono font-bold text-xs text-ink tracking-tight">CODE_AGENT</div>
              <div className="text-[11px] text-ink-secondary font-sans">verification ledger</div>
            </div>
          </Link>

          {/* Navigation Items (Monospace, left-edge accent bar) */}
          <nav className="py-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2.5 font-mono text-xs transition-colors border-l-2 ${
                      isActive
                        ? 'border-accent text-ink font-semibold bg-surface-sunken/60'
                        : 'border-transparent text-ink-secondary hover:text-ink hover:bg-surface-sunken/30'
                    }`
                  }
                >
                  <Icon className="h-3.5 w-3.5 shrink-0 opacity-70" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* Footer Area: Persistent Run Ticker & Telemetry */}
        <div className="border-t border-border p-4 space-y-3 bg-surface text-xs font-mono">
          {/* Persistent Run Ticker */}
          <div className="py-1.5 px-2 bg-surface-sunken border border-border">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 shrink-0 ${
                  activeRun ? 'bg-accent animate-ping' : 'bg-status-success'
                }`}
              />
              <span className="text-[11px] text-ink truncate">
                {activeRun
                  ? `Sandbox executing (${activeRun.run_id})`
                  : 'Ledger idle // awaiting task'}
              </span>
            </div>
          </div>

          {/* System Telemetry */}
          <div className="space-y-1.5 text-[11px] text-ink-secondary">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1">
                <Activity className="h-3 w-3 text-status-success" />
                <span>api:</span>
              </span>
              <span className={health?.status === 'healthy' ? 'text-status-success font-semibold' : 'text-status-warning font-semibold'}>
                {health?.status === 'healthy' ? 'online' : 'checking...'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span>sandbox:</span>
              <span
                className={
                  health?.docker_available ? 'text-status-success font-semibold' : 'text-status-warning font-semibold'
                }
              >
                {health?.docker_available ? 'docker cgroup' : 'host fallback'}
              </span>
            </div>

            <div className="flex items-center justify-between border-t border-border pt-1.5 mt-1">
              <span className="text-ink-tertiary">v1.0.0</span>
              {health?.demo_mode && (
                <span className="px-1.5 py-0.5 bg-status-warning text-white text-[9px] font-bold uppercase tracking-wider">
                  demo
                </span>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-canvas">
        {/* Top Header Bar */}
        <header className="h-12 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs font-mono text-ink-secondary">
            <span className="text-ink-tertiary">ledger</span>
            <span className="text-border-strong">/</span>
            <span className="text-ink font-semibold">
              {location.pathname === '/'
                ? 'new-run'
                : location.pathname.replace('/', '')}
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px] text-ink-secondary">
            <span className="px-2 py-0.5 bg-surface-sunken border border-border text-ink">
              calibration mode
            </span>
          </div>
        </header>

        {/* Demo Mode Banner */}
        {health?.demo_mode && (
          <div className="bg-status-warning-subtle border-b border-status-warning/20 px-6 py-2 text-xs text-status-warning flex items-center justify-between shrink-0 font-mono">
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 bg-status-warning text-white uppercase text-[10px] font-bold">
                demo mode
              </span>
              <span>Ephemeral test sandbox active. Production isolation recommended.</span>
            </div>
          </div>
        )}

        {/* Workspace Body */}
        <div className="flex-1 flex overflow-hidden">
          {/* Ruled Gutter Rail: ~48px wide with faint ticks, hidden on plain Security page */}
          {!isSecurityPage && (
            <div
              className="w-12 shrink-0 border-r border-border bg-surface-sunken select-none relative overflow-hidden flex flex-col justify-between py-6 z-0"
              aria-hidden="true"
            >
              {/* Vertical tick marks at 24px intervals */}
              <div className="absolute inset-0 opacity-40 bg-[repeating-linear-gradient(to_bottom,transparent_0px,transparent_23px,var(--color-rule)_23px,var(--color-rule)_24px)]" />
              {/* Right edge ticks */}
              <div className="absolute right-0 top-0 bottom-0 w-2 opacity-70 bg-[repeating-linear-gradient(to_bottom,transparent_0px,transparent_7px,var(--color-rule-strong)_7px,var(--color-rule-strong)_8px)]" />
              <div className="relative font-mono text-[9px] text-ink-tertiary rotate-90 origin-left translate-x-5 mt-4 tracking-widest uppercase">
                GUTTER // 48PX
              </div>
            </div>
          )}

          {/* Main Content Area */}
          <main className="flex-1 overflow-y-auto p-6 lg:p-8">
            <div
              className={
                isSecurityPage
                  ? 'max-w-[720px] mx-auto py-2'
                  : 'max-w-[880px]'
              }
            >
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
