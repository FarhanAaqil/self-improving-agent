import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Command, KeyRound, Moon, Sun } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getStoredApiKey, getUsage, listRuns } from '../api/client'
import { useHealth } from '../hooks/useHealth'
import { usePreferences } from '../hooks/usePreferences'
import BrandLogo from './BrandLogo'
import { NAV_ITEMS } from './nav'
import { Kbd, Meter } from './ui'

function useHotkey(handler: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        handler()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handler])
}

// Only needed once opened, so they stay out of the first download
const ApiKeyDialog = lazy(() => import('./ApiKeyDialog'))
const CommandPalette = lazy(() => import('./CommandPalette'))

export default function AppShell() {
  const location = useLocation()
  const queryClient = useQueryClient()
  const { data: health } = useHealth()
  const { isDark, update } = usePreferences()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [keyOpen, setKeyOpen] = useState(false)
  const [hasKey, setHasKey] = useState(() => Boolean(getStoredApiKey()))
  const needsKey = health?.auth === 'key' && !hasKey

  useHotkey(() => setPaletteOpen(true))

  const { data: active } = useQuery({
    queryKey: ['runs-active'],
    queryFn: () => listRuns({ pageSize: 3, status: 'running' }),
    // Quick while something is running, relaxed when idle (and paused in background tabs)
    refetchInterval: (q) => (q.state.data?.items.length ? 4000 : 20000),
    enabled: !needsKey,
  })
  const liveRun = active?.items[0]
  const { data: usage } = useQuery({
    queryKey: ['usage'],
    queryFn: getUsage,
    refetchInterval: 15000,
    enabled: !needsKey && Boolean(health?.daily_token_budget),
  })

  return (
    <div className="min-h-screen bg-canvas text-ink lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:bg-surface focus:p-2">
        Skip to content
      </a>

      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface lg:flex">
        <Link to="/" className="border-b border-border px-4 py-3.5 hover:bg-surface-sunken">
          <BrandLogo variant="full" size="md" />
        </Link>
        <nav className="flex-1 py-2" aria-label="Main">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 border-l-2 px-4 py-2.5 font-mono text-xs transition-colors ${
                  isActive
                    ? 'border-accent bg-surface-sunken font-semibold text-ink'
                    : 'border-transparent text-ink-secondary hover:bg-surface-sunken/60 hover:text-ink'
                }`
              }
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t border-border p-3 font-mono text-[11px]">
          {liveRun ? (
            <Link to={`/runs/${liveRun.run_id}`} className="flex items-center gap-2 border border-accent/40 bg-accent-subtle px-2 py-1.5 text-accent-ink">
              <span className="h-2 w-2 shrink-0 animate-breathe bg-accent" aria-hidden />
              <span className="truncate">working on {liveRun.run_id}</span>
            </Link>
          ) : (
            <div className="flex items-center gap-2 border border-border bg-surface-sunken px-2 py-1.5 text-ink-secondary">
              <span className="h-2 w-2 shrink-0 bg-status-success" aria-hidden />
              idle, ready for a task
            </div>
          )}
          <dl className="grid grid-cols-2 gap-y-1 text-ink-secondary">
            <dt>api</dt>
            <dd className={`text-right ${health ? 'text-status-success' : 'text-status-warning'}`}>{health ? 'online' : 'checking'}</dd>
            <dt>sandbox</dt>
            <dd className={`text-right ${health?.docker_available ? 'text-status-success' : 'text-status-danger'}`}>
              {health?.docker_available ? 'docker' : 'offline'}
            </dd>
            <dt>memory</dt>
            <dd className={`text-right ${health?.memory_enabled ? 'text-cyan' : 'text-ink-muted'}`}>{health?.memory_enabled ? 'on' : 'off'}</dd>
          </dl>
          {usage?.daily_budget ? (
            <div>
              <div className="flex justify-between text-ink-secondary">
                <span>tokens today</span>
                <span className="tabular-nums">{Math.round((usage.tokens_today / usage.daily_budget) * 100)}%</span>
              </div>
              <div className="mt-1"><Meter value={usage.tokens_today / usage.daily_budget} tone={usage.remaining ? 'accent' : 'cyan'} label="Daily token budget used" /></div>
            </div>
          ) : null}
          <div className="text-ink-muted">v{health?.version ?? '…'}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center justify-between gap-2 border-b border-border bg-surface/95 px-4 backdrop-blur lg:px-6">
          <Link to="/" className="lg:hidden" aria-label="Home">
            <BrandLogo variant="icon" size="sm" />
          </Link>
          <div className="hidden font-mono text-xs text-ink-muted lg:block">
            ledger <span className="text-border-strong">/</span>{' '}
            <span className="font-semibold text-ink">{location.pathname === '/' ? 'workbench' : location.pathname.slice(1)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={() => setPaletteOpen(true)} className="btn-ghost hidden px-2 py-1 sm:inline-flex" aria-label="Command palette, Ctrl K">
              <Command className="h-3.5 w-3.5" aria-hidden />
              <Kbd>Ctrl K</Kbd>
            </button>
            {health?.auth === 'key' && (
              <button
                type="button"
                onClick={() => setKeyOpen(true)}
                className={`btn px-2 py-1 ${needsKey ? 'border border-accent bg-accent-subtle text-accent-ink' : 'btn-ghost'}`}
                aria-label={needsKey ? 'key needed: add API key' : 'key set: change API key'}
              >
                <KeyRound className="h-3.5 w-3.5" aria-hidden />
                <span className="hidden sm:inline">{needsKey ? 'key needed' : 'key set'}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => update({ theme: isDark ? 'light' : 'dark' })}
              className="btn-ghost px-2 py-1"
              aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {isDark ? <Sun className="h-3.5 w-3.5" aria-hidden /> : <Moon className="h-3.5 w-3.5" aria-hidden />}
            </button>
          </div>
        </header>

        {health?.demo_mode && (
          <div className="border-b border-status-warning/30 bg-status-warning-subtle px-4 py-2 font-mono text-xs text-status-warning lg:px-6">
            Demo deployment{health.docker_available ? '' : ': no Docker here, so code execution is switched off'}.
          </div>
        )}
        {needsKey && (
          <div className="border-b border-accent/30 bg-accent-subtle px-4 py-2 text-sm text-accent-ink lg:px-6">
            This server needs an API key.{' '}
            <button type="button" className="font-semibold underline" onClick={() => setKeyOpen(true)}>
              Add it
            </button>{' '}
            to start runs.
          </div>
        )}

        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-6 lg:px-8 lg:pb-10">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-border bg-surface lg:hidden" aria-label="Main">
        {NAV_ITEMS.map(({ to, short, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 py-2 font-mono text-[10px] ${isActive ? 'text-accent-ink' : 'text-ink-muted'}`
            }
          >
            <Icon className="h-4 w-4" aria-hidden />
            {short}
          </NavLink>
        ))}
      </nav>

      <Suspense fallback={null}>
        {paletteOpen && <CommandPalette open onClose={() => setPaletteOpen(false)} />}
        {keyOpen && (
          <ApiKeyDialog
            open
            onClose={() => setKeyOpen(false)}
            onSaved={() => {
              setHasKey(Boolean(getStoredApiKey()))
              queryClient.invalidateQueries()
            }}
          />
        )}
      </Suspense>
    </div>
  )
}
