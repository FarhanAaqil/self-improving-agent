import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, OctagonX, PauseCircle } from 'lucide-react'
import { statusMeta } from '../lib/format'

const TONES = {
  success: 'border-status-success/40 bg-status-success-subtle text-status-success',
  danger: 'border-status-danger/40 bg-status-danger-subtle text-status-danger',
  warning: 'border-status-warning/40 bg-status-warning-subtle text-status-warning',
  accent: 'border-accent/40 bg-accent-subtle text-accent-ink',
  muted: 'border-border bg-surface-sunken text-ink-secondary',
  cyan: 'border-cyan/40 bg-cyan-subtle text-cyan',
}

export type Tone = keyof typeof TONES

/** Status always pairs an icon and a word with its color, never color alone. */
export function StatusPill({ status, className = '' }: { status?: string | null; className?: string }) {
  const { label, tone } = statusMeta(status)
  const Icon =
    tone === 'success' ? CheckCircle2
      : tone === 'danger' ? OctagonX
        : tone === 'warning' ? PauseCircle
          : tone === 'accent' ? Loader2
            : CircleDashed
  return (
    <span className={`chip ${TONES[tone]} ${className}`}>
      <Icon className={`h-3 w-3 ${tone === 'accent' ? 'animate-spin' : ''}`} aria-hidden />
      {label}
    </span>
  )
}

export function Chip({ tone = 'muted', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`chip ${TONES[tone]} ${className}`}>{children}</span>
}

export function PageHeader({
  eyebrow,
  title,
  lede,
  actions,
}: {
  eyebrow: string
  title: ReactNode
  lede?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="mt-1 font-mono text-2xl font-bold tracking-tight text-ink sm:text-[28px]">{title}</h1>
        {lede && <p className="mt-1.5 max-w-2xl text-sm text-ink-secondary">{lede}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function Panel({
  title,
  icon,
  actions,
  children,
  className = '',
  bodyClassName = 'p-4',
}: {
  title?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <h2 className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-ink">
            {icon}
            {title}
          </h2>
          {actions}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'accent' | 'cyan' | 'success' }) {
  const color = tone === 'accent' ? 'text-accent-ink' : tone === 'cyan' ? 'text-cyan' : tone === 'success' ? 'text-status-success' : 'text-ink'
  return (
    <div className="panel px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className={`mt-1 font-mono text-2xl font-bold tabular-nums ${color}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-muted">{hint}</div>}
    </div>
  )
}

export function Meter({ value, tone = 'accent', label }: { value: number | null | undefined; tone?: 'accent' | 'cyan' | 'success'; label: string }) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value)) * 100
  const fill = tone === 'cyan' ? 'bg-cyan' : tone === 'success' ? 'bg-status-success' : 'bg-accent'
  return (
    <div role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
      <div className="h-1.5 w-full bg-surface-sunken">
        <div className={`h-full ${fill} transition-[width] duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="panel grid-paper flex flex-col items-center px-6 py-14 text-center">
      {icon && <div className="mb-3 text-ink-tertiary">{icon}</div>}
      <h3 className="font-mono text-sm font-bold text-ink">{title}</h3>
      {children && <p className="mt-1.5 max-w-md text-sm text-ink-secondary">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="flex items-start gap-3 border border-status-danger/30 bg-status-danger-subtle p-3 text-sm text-status-danger">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{message}</div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-mono text-xs font-bold uppercase underline">
          retry
        </button>
      )}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="border border-border-strong bg-surface-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-secondary">
      {children}
    </kbd>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-surface-sunken ${className}`} />
}
