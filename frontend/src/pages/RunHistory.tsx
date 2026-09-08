import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  AlertCircle,
  Clock,
  ExternalLink,
  Filter,
  History,
  Layers,
  Loader2,
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <History className="h-6 w-6 text-indigo-400" />
            <span>Run History</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Historical log of code generation and autonomous repair sessions.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300 transition-colors disabled:opacity-50 cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 text-xs">
          <Filter className="h-3.5 w-3.5 text-slate-500 shrink-0 ml-1" />
          {[
            { id: 'all', label: 'All Runs' },
            { id: 'success', label: 'Success' },
            { id: 'failed', label: 'Failed' },
            { id: 'running', label: 'Running' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setStatusFilter(item.id)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer shrink-0 ${
                statusFilter === item.id
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/20'
                  : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="relative min-w-[240px]">
          <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by run ID or task..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="p-12 border border-slate-800 rounded-xl bg-slate-900/30 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          <div className="text-sm text-slate-400">Loading run history from SQLite...</div>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-rose-400" />
          <div>
            <div className="font-semibold">Failed to fetch run history</div>
            <div className="text-xs text-rose-300/80 font-mono mt-0.5">
              {error instanceof Error ? error.message : 'Unknown network error'}
            </div>
          </div>
        </div>
      )}

      {/* Table view */}
      {!isLoading && !isError && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase font-mono tracking-wider">
                <tr>
                  <th className="py-3 px-4">Run ID</th>
                  <th className="py-3 px-4">Task Description</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Attempts</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredRuns.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500 italic">
                      No matching runs found in database.
                    </td>
                  </tr>
                ) : (
                  filteredRuns.map((run) => (
                    <tr key={run.run_id} className="hover:bg-slate-850/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">
                        <Link
                          to={`/runs/${run.run_id}`}
                          className="text-indigo-400 hover:text-indigo-300 hover:underline"
                        >
                          {run.run_id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 max-w-md truncate text-slate-300" title={run.task_description}>
                        {run.task_description}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={run.final_status} size="sm" />
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-400">
                        {run.total_attempts} attempt{run.total_attempts === 1 ? '' : 's'}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">
                        {run.created_at ? new Date(run.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/runs/${run.run_id}`}
                          className="inline-flex items-center gap-1 text-slate-400 hover:text-indigo-400 font-medium transition-colors"
                        >
                          <span>View</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
