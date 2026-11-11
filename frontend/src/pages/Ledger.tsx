import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, History, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api/client'
import { EmptyState, ErrorNote, PageHeader, Skeleton, Stat, StatusPill } from '../components/ui'
import { compactNumber, duration, relativeTime, score10 } from '../lib/format'

const FILTERS = [
  { id: 'all', label: 'all' },
  { id: 'success', label: 'verified' },
  { id: 'failed', label: 'unsolved' },
  { id: 'early_stopped', label: 'stopped early' },
  { id: 'running', label: 'running' },
]

export default function Ledger() {
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 15

  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 350)
    return () => clearTimeout(id)
  }, [search])

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['runs', page, q, status],
    queryFn: () => listRuns({ page, pageSize, q, status }),
    placeholderData: keepPreviousData,
    // Only poll quickly while a listed run can still change
    refetchInterval: (q) =>
      q.state.data?.items.some((r) => ['running', 'queued'].includes(r.final_status)) ? 5000 : 30000,
  })

  const counts = data?.status_counts ?? {}
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const verified = counts.success ?? 0
  const unsolved = (counts.failed ?? 0) + (counts.max_retries_exceeded ?? 0) + (counts.early_stopped ?? 0)
  const pages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="ledger" title="Every run, on the record" lede="Each entry is a task I took on, how many attempts it needed, and whether the result was verified in the sandbox." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="runs" value={total} />
        <Stat label="verified" value={verified} tone="success" hint={total ? `${Math.round((verified / total) * 100)}% of all runs` : undefined} />
        <Stat label="unsolved" value={unsolved} />
        <Stat label="running now" value={(counts.running ?? 0) + (counts.queued ?? 0)} tone="accent" />
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={status === f.id}
              onClick={() => { setStatus(f.id); setPage(1) }}
              className={`chip px-2.5 py-1 ${status === f.id ? 'border-ink bg-ink text-ink-inverse' : 'border-border bg-surface text-ink-secondary hover:text-ink'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="relative md:w-72">
          <span className="sr-only">Search runs</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" aria-hidden />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="search tasks or run ids" className="input pl-8 font-mono text-xs" />
        </label>
      </div>

      {error && <ErrorNote error={error} onRetry={() => refetch()} />}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState icon={<History className="h-8 w-8" />} title={q || status !== 'all' ? 'Nothing matches that' : 'The ledger is empty'} action={<Link to="/" className="btn-primary">start a run</Link>}>
          {q || status !== 'all' ? 'Try a different filter or search.' : 'Every task you give me is recorded here with its attempts and verification.'}
        </EmptyState>
      ) : (
        <>
          {/* Desktop table */}
          <div className="panel hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <caption className="sr-only">Runs</caption>
              <thead className="border-b border-border bg-surface-sunken font-mono text-[11px] uppercase tracking-wider text-ink-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 text-left font-medium">status</th>
                  <th scope="col" className="px-4 py-2 text-left font-medium">task</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">attempts</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">quality</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">sandbox</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">tokens</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">when</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((r) => (
                  <tr key={r.run_id} className="group hover:bg-surface-sunken/60">
                    <td className="px-4 py-2.5"><StatusPill status={r.final_status} /></td>
                    <td className="max-w-md px-4 py-2.5">
                      <Link to={`/runs/${r.run_id}`} className="line-clamp-1 text-ink group-hover:text-accent-ink" title={r.task_description}>
                        {r.task_description}
                      </Link>
                      <div className="font-mono text-[10px] text-ink-muted">{r.run_id} · {r.model_name ?? '—'}</div>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                      {r.total_attempts}
                      {r.passed_on_attempt ? <span className="text-ink-muted"> (✓{r.passed_on_attempt})</span> : null}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">{score10(r.quality_score)}</td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-secondary">{duration(r.total_latency_ms)}</td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-secondary">{compactNumber((r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0))}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-[11px] text-ink-muted">{relativeTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <ul className="space-y-2 md:hidden">
            {data.items.map((r) => (
              <li key={r.run_id}>
                <Link to={`/runs/${r.run_id}`} className="panel block p-3">
                  <div className="flex items-center justify-between gap-2">
                    <StatusPill status={r.final_status} />
                    <span className="font-mono text-[11px] text-ink-muted">{relativeTime(r.created_at)}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-ink">{r.task_description}</p>
                  <div className="mt-2 flex gap-4 font-mono text-[11px] text-ink-muted">
                    <span>{r.total_attempts} attempt{r.total_attempts === 1 ? '' : 's'}</span>
                    <span>quality {score10(r.quality_score)}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>

          <nav className="flex items-center justify-between font-mono text-xs text-ink-secondary" aria-label="Pagination">
            <span>{data.total} runs · page {page} of {pages}</span>
            <div className="flex gap-1">
              <button type="button" className="btn-secondary px-2 py-1" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button type="button" className="btn-secondary px-2 py-1" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                <ChevronRight className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          </nav>
        </>
      )}
    </div>
  )
}
