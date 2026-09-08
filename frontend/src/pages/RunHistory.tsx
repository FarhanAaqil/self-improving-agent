import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Filter,
  History,
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink flex items-center gap-2.5">
            <History className="h-5 w-5 text-accent" />
            <span>Run History</span>
          </h1>
          <p className="text-sm text-ink-secondary mt-1">
            Historical audit log of code generation and autonomous repair sessions.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-surface hover:bg-canvas border border-border text-xs font-medium text-ink transition-colors disabled:opacity-50 cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-accent' : 'text-ink-tertiary'}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-surface border border-border rounded p-3 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 text-xs">
          <Filter className="h-3.5 w-3.5 text-ink-tertiary shrink-0 ml-1" />
          {[
            { id: 'all', label: 'All runs' },
            { id: 'success', label: 'Success' },
            { id: 'failed', label: 'Failed' },
            { id: 'running', label: 'Running' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setStatusFilter(item.id)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
                statusFilter === item.id
                  ? 'bg-accent-subtle text-accent border border-accent/30 font-semibold'
                  : 'text-ink-secondary hover:text-ink hover:bg-surface-sunken'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-64">
          <Search className="h-3.5 w-3.5 text-ink-tertiary absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search run ID or task..."
            className="w-full pl-8 pr-3 py-1.5 bg-surface-sunken border border-border rounded text-xs text-ink placeholder-ink-tertiary focus:outline-none focus:border-accent focus:bg-surface transition-all font-sans"
          />
        </div>
      </div>

      {/* Runs Table */}
      <div className="bg-surface border border-border rounded overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-xs text-ink-secondary font-mono">
            Loading run history from SQLite database...
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-xs text-status-danger flex items-center justify-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>Failed to load run history: {error instanceof Error ? error.message : 'Network error'}</span>
          </div>
        ) : paginatedRuns.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-secondary space-y-1">
            <div className="font-medium text-ink">No execution runs found</div>
            <div className="text-ink-tertiary">Try adjusting your status filter or submit a new run.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface-sunken text-ink-secondary font-medium select-none">
                  <th className="py-2.5 px-4 font-mono">Run ID</th>
                  <th className="py-2.5 px-4">Task Description</th>
                  <th className="py-2.5 px-4 font-mono">Attempts</th>
                  <th className="py-2.5 px-4 font-mono">Quality</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 font-mono">Created</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paginatedRuns.map((run, idx) => {
                  const passingAttempt = run.attempts.find((a) => a.success)
                  const lastAttempt = run.attempts[run.attempts.length - 1]
                  const qualityScore =
                    passingAttempt?.quality_overall_score ?? lastAttempt?.quality_overall_score

                  return (
                    <tr
                      key={run.run_id}
                      className={`hover:bg-accent-subtle/40 transition-colors ${
                        idx % 2 === 1 ? 'bg-surface-sunken/40' : 'bg-surface'
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-accent font-medium">
                        <Link to={`/runs/${run.run_id}`} className="hover:underline">
                          {run.run_id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 max-w-md">
                        <div className="line-clamp-1 text-ink" title={run.task_description}>
                          {run.task_description}
                        </div>
                      </td>
                      <td className="py-3 px-4 font-mono text-ink-secondary">
                        {run.attempts.length} / {run.total_attempts || 3}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {qualityScore !== null && qualityScore !== undefined ? (
                          <span
                            className={`font-semibold ${
                              qualityScore >= 8
                                ? 'text-status-success'
                                : qualityScore >= 6
                                ? 'text-status-warning'
                                : 'text-status-danger'
                            }`}
                          >
                            {qualityScore.toFixed(1)}/10
                          </span>
                        ) : (
                          <span className="text-ink-tertiary">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={run.final_status} size="sm" />
                      </td>
                      <td className="py-3 px-4 font-mono text-ink-tertiary">
                        {run.created_at
                          ? new Date(run.created_at).toLocaleDateString(undefined, {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/runs/${run.run_id}`}
                          className="inline-flex items-center gap-1 text-accent hover:text-accent-hover font-medium"
                        >
                          <span>Detail</span>
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
          <div className="px-4 py-3 border-t border-border bg-surface flex items-center justify-between text-xs text-ink-secondary">
            <div>
              Showing <span className="font-mono text-ink">{startIndex + 1}</span> to{' '}
              <span className="font-mono text-ink">{endIndex}</span> of{' '}
              <span className="font-mono text-ink">{totalItems}</span> runs
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <span>Per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="bg-surface-sunken border border-border rounded px-1.5 py-0.5 text-xs font-mono text-ink focus:outline-none"
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
                  className="p-1 rounded hover:bg-surface-sunken disabled:opacity-30 disabled:cursor-not-allowed text-ink cursor-pointer border border-border"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <span className="font-mono text-xs px-2">
                  {currentPage} / {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 rounded hover:bg-surface-sunken disabled:opacity-30 disabled:cursor-not-allowed text-ink cursor-pointer border border-border"
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
