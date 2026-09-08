import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Code2,
  ExternalLink,
  Layers,
  Loader2,
  RefreshCw,
  Scale,
  Terminal,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getRun } from '../api/client'
import type { RunOut } from '../api/types'
import AttemptCard from '../components/AttemptCard'
import CodeDiffView from '../components/CodeDiffView'
import StatusBadge from '../components/StatusBadge'

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()

  const {
    data: run,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<RunOut>({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!),
    enabled: Boolean(runId),
  })

  if (isLoading) {
    return (
      <div className="p-16 border border-slate-800 rounded-xl bg-slate-900/30 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
        <div className="text-sm text-slate-400">Loading run detail for {runId}...</div>
      </div>
    )
  }

  if (isError || !run) {
    return (
      <div className="space-y-4">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>
        <div className="p-6 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="h-5 w-5 text-rose-400" />
            <span>Run Not Found</span>
          </div>
          <div className="text-xs text-rose-300/80 font-mono">
            {error instanceof Error ? error.message : `No records found in database for run '${runId}'.`}
          </div>
        </div>
      </div>
    )
  }

  const totalLatency = run.attempts.reduce((sum, a) => sum + (a.latency_ms || 0), 0)
  const passingAttempt = run.attempts.find((a) => a.success)
  const latestAttempt = run.attempts[run.attempts.length - 1]

  // Check if early-stop was triggered by Critique agent (confidence < 0.3)
  const isEarlyStopped =
    latestAttempt &&
    latestAttempt.critique_confidence !== null &&
    latestAttempt.critique_confidence !== undefined &&
    latestAttempt.critique_confidence < 0.3 &&
    !latestAttempt.success

  return (
    <div className="space-y-6">
      {/* Top navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300 transition-colors cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Run Summary Header Card */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-base font-bold text-slate-100">{run.run_id}</span>
                <StatusBadge status={run.final_status} />
              </div>
              <div className="text-xs text-slate-500 font-mono mt-0.5">
                Created: {run.created_at ? new Date(run.created_at).toLocaleString() : 'Unknown'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Attempts</span>
              <span className="text-slate-200 font-bold">{run.total_attempts}</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Total Latency</span>
              <span className="text-slate-200 font-bold">{totalLatency}ms</span>
            </div>
          </div>
        </div>

        {/* Task description */}
        <div>
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Task Prompt
          </div>
          <p className="text-sm text-slate-200 font-mono bg-slate-950/80 p-3 rounded-lg border border-slate-800 leading-relaxed whitespace-pre-wrap">
            {run.task_description}
          </p>
        </div>
      </div>

      {/* Critique Reasoning & Early-Stop Display */}
      {latestAttempt?.critique_confidence !== null &&
        latestAttempt?.critique_confidence !== undefined && (
          <div
            className={`p-4 rounded-xl border flex items-start gap-3.5 text-xs ${
              isEarlyStopped
                ? 'bg-amber-950/20 border-amber-500/30 text-amber-200'
                : 'bg-indigo-950/20 border-indigo-500/30 text-indigo-200'
            }`}
          >
            <Scale className="h-5 w-5 shrink-0 text-indigo-400 mt-0.5" />
            <div className="space-y-1 flex-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-100">
                  Critique Evaluation Analysis
                </span>
                <span className="font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300">
                  Confidence: {(latestAttempt.critique_confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-slate-400 leading-relaxed font-sans">
                {isEarlyStopped
                  ? 'Early-stop triggered: The Critique agent assessed confidence below 0.3 threshold, terminating the repair loop early to avoid wasteful token consumption on intractable errors.'
                  : `Critique score ${(latestAttempt.critique_confidence * 100).toFixed(0)}% exceeds the 0.3 threshold. Code verified against quality and execution constraints.`}
              </p>
            </div>
          </div>
        )}

      {/* Code diff view between attempts if 2 or more attempts exist */}
      {run.attempts.length >= 2 && <CodeDiffView attempts={run.attempts} />}

      {/* Attempts Timeline */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Terminal className="h-4 w-4 text-indigo-400" />
            <span>Attempt History ({run.attempts.length})</span>
          </h2>
          {passingAttempt && (
            <span className="text-xs text-emerald-400 font-mono">
              Passed on Attempt #{passingAttempt.attempt_number}
            </span>
          )}
        </div>

        {run.attempts.length === 0 ? (
          <div className="p-8 border border-slate-800 rounded-xl bg-slate-900/30 text-center text-xs text-slate-500 italic">
            No execution attempts recorded for this run.
          </div>
        ) : (
          <div className="space-y-3">
            {run.attempts.map((attempt) => (
              <AttemptCard
                key={attempt.attempt_id ?? attempt.attempt_number}
                attempt={attempt}
                defaultExpanded={attempt.attempt_number === run.attempts.length}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
