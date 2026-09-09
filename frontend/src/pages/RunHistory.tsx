import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Filter,
  RefreshCw,
  Search,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api/client'
import type { RunOut } from '../api/types'
import StatusBadge from '../components/StatusBadge'

export default function RunHistory() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const {
    data: runs = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<RunOut[]>({
    queryKey: ['runs'],
    queryFn: () => listRuns(100),
    refetchInterval: 10000,
  })

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, searchQuery, pageSize])

  const filteredRuns = runs.filter((run) => {
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'success' && run.final_status === 'success') ||
      (statusFilter === 'failed' &&
        (run.final_status === 'failed' || run.final_status === 'max_retries_exceeded')) ||
      (statusFilter === 'running' && run.final_status === 'running')

    const matchesSearch =
      !searchQuery.trim() ||
      run.run_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      run.task_description.toLowerCase().includes(searchQuery.toLowerCase())

    return matchesStatus && matchesSearch
  })

  const totalItems = filteredRuns.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, totalItems)
  const paginatedRuns = filteredRuns.slice(startIndex, endIndex)

  // Aggregate stats
  const totalRuns = runs.length
  const successRuns = runs.filter((r) => r.final_status === 'success').length
  const failedRuns = runs.filter(
    (r) => r.final_status === 'failed' || r.final_status === 'max_retries_exceeded'
  ).length
  const runningRuns = runs.filter((r) => r.final_status === 'running').length
  const successRate = totalRuns > 0 ? Math.round((successRuns / totalRuns) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="flex items-start gap-3.5">
          <div className="relative shrink-0 h-10 w-10 bg-[#10241C] border border-accent/40 flex items-center justify-center shadow-xs">
            <img src="/logo-square.jpg" alt="CODE_AGENT" className="h-9 w-9 object-cover" />
            <span className="absolute top-0 right-0 h-1.5 w-1.5 bg-accent" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-mono font-bold tracking-tight text-ink">
                run history
              </h1>
              <span className="text-[10px] font-mono px-1.5 py-0.5 bg-surface-sunken border border-border text-ink-tertiary">
                AUDIT LEDGER
              </span>
            </div>
            <p className="text-xs text-ink-secondary mt-0.5 font-sans">
              Audit ledger of synthesized programs, sandbox test tracebacks, and repair sessions.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-3 py-2 bg-surface hover:bg-surface-sunken border border-border-strong text-xs font-mono text-ink transition-colors disabled:opacity-50 cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-accent' : 'text-ink-tertiary'}`} />
          <span>refresh</span>
        </button>
      </div>

      {/* Stats Bar */}
      {!isLoading && !isError && totalRuns > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'total runs', value: totalRuns, color: 'text-ink' },
            { label: 'passed', value: successRuns, color: 'text-status-success' },
            { label: 'failed', value: failedRuns, color: 'text-status-danger' },
            { label: 'success rate', value: `${successRate}%`, color: 'text-accent' },
          ].map((stat) => (
            <div key={stat.label} className="bg-surface border border-border p-3">
              <div className={`text-2xl font-mono font-bold ${stat.color}`}>{stat.value}</div>
              <div className="text-[11px] text-ink-tertiary font-mono uppercase tracking-wider mt-0.5">{stat.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Active-run banner */}
      {runningRuns > 0 && (
        <div className="bg-accent-subtle border border-accent/30 px-4 py-2.5 flex items-center gap-2.5 text-xs font-mono">
          <span className="h-2 w-2 bg-accent animate-ping shrink-0" />
          <span className="text-accent font-bold">{runningRuns} run{runningRuns > 1 ? 's' : ''} actively executing</span>
          <span className="text-ink-secondary">— auto-refreshes every 10s</span>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="bg-surface border border-border p-3 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 text-xs font-mono">
          <Filter className="h-3.5 w-3.5 text-ink-tertiary shrink-0 ml-1" />
          {[
            { id: 'all', label: 'all runs' },
            { id: 'success', label: 'success' },
            { id: 'failed', label: 'failed' },
            { id: 'running', label: 'running' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setStatusFilter(item.id)}
              className={`px-3 py-1 text-xs font-mono border transition-colors cursor-pointer ${
                statusFilter === item.id
                  ? 'bg-ink text-surface border-ink font-bold'
                  : 'border-border text-ink-secondary hover:text-ink hover:bg-surface-sunken'
              }`}
            >
              {item.label}
              {item.id === 'all' && totalRuns > 0 && (
                <span className="ml-1.5 font-mono text-[10px] opacity-60">{totalRuns}</span>
              )}
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-64">
          <Search className="h-3.5 w-3.5 text-ink-tertiary absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="search run ID or prompt..."
            className="w-full pl-8 pr-3 py-1.5 bg-surface-sunken border border-border text-xs text-ink placeholder-ink-tertiary focus:outline-none focus:border-accent focus:bg-surface transition-all font-mono"
          />
        </div>
      </div>

      {/* Runs Table */}
      <div className="bg-surface border border-border overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-xs text-ink-secondary font-mono space-y-2">
            <div className="h-5 w-5 border-2 border-accent border-t-transparent animate-spin mx-auto" />
            <div>loading audit ledger from SQLite database...</div>
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-xs font-mono text-status-danger flex items-center justify-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>failed to load run history: {error instanceof Error ? error.message : 'network error'}</span>
          </div>
        ) : paginatedRuns.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-secondary space-y-3 font-mono">
            <div className="relative h-12 w-12 bg-[#10241C] border border-border mx-auto flex items-center justify-center p-1 shadow-xs">
              <img src="/logo-square.jpg" alt="No runs" className="h-10 w-10 object-cover opacity-60" />
              <span className="absolute top-0 right-0 h-1.5 w-1.5 bg-accent/60" />
            </div>
            <div className="font-bold text-ink">
              {searchQuery || statusFilter !== 'all' ? 'no matching runs' : 'no execution runs recorded'}
            </div>
            <div className="text-ink-tertiary font-sans text-sm max-w-sm mx-auto">
              {searchQuery || statusFilter !== 'all'
                ? 'Try adjusting your filters or search query.'
                : 'Submit a new task to synthesize solutions and audit in sandbox.'}
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface-sunken text-ink-secondary font-mono text-[11px] select-none uppercase tracking-wider">
                  <th className="py-2.5 px-4">run id</th>
                  <th className="py-2.5 px-4">task specification</th>
                  <th className="py-2.5 px-4">attempts</th>
                  <th className="py-2.5 px-4">quality</th>
                  <th className="py-2.5 px-4">status</th>
                  <th className="py-2.5 px-4">timestamp</th>
                  <th className="py-2.5 px-4 text-right">ledger</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paginatedRuns.map((run, idx) => {
                  const attempts = run.attempts ?? []
                  const passingAttempt = attempts.find((a) => a.success)
                  const lastAttempt = attempts[attempts.length - 1]
                  const qualityScore =
                    passingAttempt?.quality_overall_score ?? lastAttempt?.quality_overall_score

                  return (
                    <tr
                      key={run.run_id}
                      className={`hover:bg-accent-subtle/20 transition-colors group ${
                        idx % 2 === 1 ? 'bg-surface-sunken/30' : 'bg-surface'
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-accent font-bold relative">
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-[1px] bg-border-strong" />
                        <Link to={`/runs/${run.run_id}`} className="hover:underline group-hover:text-accent-hover transition-colors">
                          {run.run_id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 max-w-xs font-sans">
                        <div className="line-clamp-1 text-ink" title={run.task_description}>
                          {run.task_description}
                        </div>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        <span className="text-ink font-bold">{attempts.length}</span>
                        <span className="text-ink-tertiary">/{run.total_attempts || 3}</span>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {qualityScore !== null && qualityScore !== undefined ? (
                          <span className={`font-bold ${
                            qualityScore >= 8 ? 'text-status-success'
                              : qualityScore >= 6 ? 'text-status-warning'
                              : 'text-status-danger'
                          }`}>
                            {qualityScore.toFixed(1)}<span className="text-ink-tertiary font-normal">/10</span>
                          </span>
                        ) : (
                          <span className="text-ink-tertiary">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={run.final_status} size="sm" />
                      </td>
                      <td className="py-3 px-4 font-mono text-ink-tertiary text-[11px]">
                        {run.created_at
                          ? new Date(run.created_at).toLocaleDateString(undefined, {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        <Link
                          to={`/runs/${run.run_id}`}
                          className="inline-flex items-center gap-1 text-accent hover:text-accent-hover font-bold transition-colors"
                        >
                          <span>inspect</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!isLoading && filteredRuns.length > 0 && (
          <div className="px-4 py-3 border-t border-border bg-surface flex items-center justify-between text-xs font-mono text-ink-secondary">
            <div>
              showing <span className="text-ink font-bold">{startIndex + 1}</span> to{' '}
              <span className="text-ink font-bold">{endIndex}</span> of{' '}
              <span className="text-ink font-bold">{totalItems}</span> runs
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <span>per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="bg-surface-sunken border border-border px-1.5 py-0.5 text-xs font-mono text-ink focus:outline-none"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1 hover:bg-surface-sunken disabled:opacity-30 disabled:cursor-not-allowed text-ink cursor-pointer border border-border"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <span className="font-mono text-xs px-2 text-ink">
                  {currentPage} / {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 hover:bg-surface-sunken disabled:opacity-30 disabled:cursor-not-allowed text-ink cursor-pointer border border-border"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
