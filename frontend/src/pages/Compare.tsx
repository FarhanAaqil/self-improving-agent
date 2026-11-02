import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Swords, Trophy } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getComparison } from '../api/client'
import { isTerminalStatus, type RunSummary } from '../api/types'
import { Chip, EmptyState, PageHeader, Skeleton, StatusPill } from '../components/ui'
import { compactNumber, duration, score10 } from '../lib/format'

/** Lower is better for attempts, tokens and time; higher for quality. Ties go to fewer tokens. */
function pickWinner(runs: RunSummary[]): string | null {
  const solved = runs.filter((r) => r.final_status === 'success')
  if (!solved.length || runs.some((r) => !isTerminalStatus(r.final_status))) return null
  const tokens = (r: RunSummary) => (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0)
  return [...solved].sort(
    (a, b) =>
      (a.passed_on_attempt ?? 99) - (b.passed_on_attempt ?? 99) ||
      (b.quality_score ?? 0) - (a.quality_score ?? 0) ||
      tokens(a) - tokens(b),
  )[0].run_id
}

export default function Compare() {
  const { groupId } = useParams<{ groupId: string }>()
  const { data, isLoading, error } = useQuery({
    queryKey: ['compare', groupId],
    queryFn: () => getComparison(groupId!),
    enabled: Boolean(groupId),
    refetchInterval: (q) => (q.state.data?.runs.every((r) => isTerminalStatus(r.final_status)) ? false : 2500),
  })

  if (isLoading) return <Skeleton className="h-96" />
  if (error || !data) {
    return <EmptyState title="Comparison not found" action={<Link to="/" className="btn-primary">start one</Link>}>{error instanceof Error ? error.message : ''}</EmptyState>
  }

  const winner = pickWinner(data.runs)
  const rows: { label: string; value: (r: RunSummary) => string }[] = [
    { label: 'passed on attempt', value: (r) => (r.passed_on_attempt ? `#${r.passed_on_attempt}` : '—') },
    { label: 'attempts used', value: (r) => String(r.total_attempts) },
    { label: 'quality', value: (r) => `${score10(r.quality_score)} / 10` },
    { label: 'tokens', value: (r) => compactNumber((r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0)) },
    { label: 'sandbox time', value: (r) => duration(r.total_latency_ms) },
  ]

  return (
    <div className="space-y-6">
      <Link to="/history" className="inline-flex items-center gap-1.5 font-mono text-xs text-ink-secondary hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> ledger
      </Link>
      <PageHeader
        eyebrow={`model race · ${data.group_id}`}
        title={<span className="flex items-center gap-2"><Swords className="h-6 w-6 text-accent" aria-hidden /> Same task, {data.runs.length} models</span>}
        lede={data.task}
      />

      <div className={`grid gap-4 ${data.runs.length >= 3 ? 'lg:grid-cols-3' : 'md:grid-cols-2'}`}>
        {data.runs.map((r) => {
          const won = r.run_id === winner
          return (
            <article key={r.run_id} className={`panel flex flex-col ${won ? 'border-status-success shadow-[inset_0_3px_0_rgb(var(--success))]' : ''}`}>
              <header className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm font-bold text-ink">{r.model_name}</div>
                  <div className="mt-1"><StatusPill status={r.final_status} /></div>
                </div>
                {won && <Chip tone="success"><Trophy className="h-3 w-3" aria-hidden /> best</Chip>}
              </header>
              <dl className="flex-1 divide-y divide-border px-4">
                {rows.map((row) => (
                  <div key={row.label} className="flex justify-between py-2 font-mono text-xs">
                    <dt className="text-ink-muted">{row.label}</dt>
                    <dd className="tabular-nums text-ink">{row.value(r)}</dd>
                  </div>
                ))}
              </dl>
              <Link to={`/runs/${r.run_id}`} className="border-t border-border px-4 py-2.5 text-center font-mono text-xs text-accent-ink hover:bg-surface-sunken">
                watch this run →
              </Link>
            </article>
          )
        })}
      </div>
      <p className="font-mono text-[11px] text-ink-muted">
        Best = verified in the fewest attempts, then highest quality, then fewest tokens.
      </p>
    </div>
  )
}
