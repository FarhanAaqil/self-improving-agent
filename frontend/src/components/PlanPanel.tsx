import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getAccountUsage } from '../api/client'
import { compactNumber, relativeTime } from '../lib/format'
import { Chip, ErrorNote, Meter, Panel, Skeleton } from './ui'

function Row({ label, used, limit, hint }: { label: string; used?: number; limit: number; hint?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-ink-secondary">{label}</span>
        <span className="font-mono tabular-nums text-ink">
          {used === undefined ? compactNumber(limit) : `${compactNumber(used)} / ${compactNumber(limit)}`}
        </span>
      </div>
      {used !== undefined && limit > 0 && (
        <div className="mt-1"><Meter value={Math.min(1, used / limit)} tone={used >= limit ? 'cyan' : 'accent'} label={label} /></div>
      )}
      {hint && <div className="mt-0.5 text-[11px] text-ink-muted">{hint}</div>}
    </div>
  )
}

export default function PlanPanel() {
  const { data, isLoading, error } = useQuery({ queryKey: ['account-usage'], queryFn: getAccountUsage, refetchInterval: 30_000 })

  return (
    <Panel
      title="plan & usage"
      actions={data && <Chip tone={data.plan.name === 'free' ? 'muted' : 'success'}>{data.plan.label}</Chip>}
    >
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : error ? (
        <ErrorNote error={error} />
      ) : data ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Row
              label="runs today"
              used={data.usage.runs_today}
              limit={data.limits.runs_per_day}
              hint={data.new_account ? 'New accounts get a lower limit for their first day.' : 'Resets at midnight, server time.'}
            />
            {data.limits.server_token_budget > 0 ? (
              <Row label="tokens on our key today" used={data.usage.server_tokens_today} limit={data.limits.server_token_budget} hint="Your own key has no cap from us." />
            ) : (
              <div className="text-sm text-ink-secondary">
                <div className="flex justify-between"><span>Groq key</span><span className="font-mono text-ink">your own</span></div>
                <div className="mt-0.5 text-[11px] text-ink-muted">The Free plan runs on your key, so it never waits on ours.</div>
              </div>
            )}
            <Row label="runs at once" limit={data.limits.concurrent_runs} hint={data.usage.queued ? `${data.usage.queued} waiting in line now` : undefined} />
            <Row label="history kept (days)" limit={data.limits.history_days} />
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-ink-secondary">
              {data.paid_until
                ? <>Paid until <span className="font-mono text-ink">{new Date(data.paid_until).toLocaleDateString()}</span> ({relativeTime(data.paid_until)}). After that you’re back on Free, with nothing lost.</>
                : 'Pro uses our key within a daily budget, runs three at a time and keeps a year of history.'}
            </p>
            {data.upgrade_url ? (
              <a href={data.upgrade_url} target="_blank" rel="noreferrer" className="btn-primary shrink-0">
                <Sparkles className="h-3.5 w-3.5" aria-hidden /> upgrade to Pro <ArrowUpRight className="h-3 w-3" aria-hidden />
              </a>
            ) : data.plan.name === 'free' ? (
              <Link to="/pricing" className="btn-secondary shrink-0">see plans</Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </Panel>
  )
}
