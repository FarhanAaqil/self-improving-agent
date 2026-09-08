import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertCircle,
  Award,
  BarChart3,
  CheckCircle2,
  Clock,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { getLatestEval } from '../api/client'
import type { EvalResultOut } from '../api/types'

export default function EvalDashboard() {
  const {
    data: evalResult,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<EvalResultOut>({
    queryKey: ['eval-latest'],
    queryFn: getLatestEval,
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <BarChart3 className="h-6 w-6 text-indigo-400" />
            <span>Evaluation & Benchmark Dashboard</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            HumanEval benchmark results, pass@k accuracy metrics, and agent reliability tracking.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300 transition-colors cursor-pointer disabled:opacity-50 self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh Results</span>
        </button>
      </div>

      {isLoading && (
        <div className="p-16 border border-slate-800 rounded-xl bg-slate-900/30 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          <div className="text-sm text-slate-400">Loading benchmark evaluation metrics...</div>
        </div>
      )}

      {isError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Failed to fetch evaluation metrics</div>
            <div className="text-xs text-rose-300/80 font-mono mt-0.5">
              {error instanceof Error ? error.message : 'Unknown network error'}
            </div>
          </div>
        </div>
      )}

      {!isLoading && !isError && evalResult && (
        <div className="space-y-6">
          {/* Key Metric Scorecards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* pass@1 */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span className="font-medium">pass@1 Accuracy</span>
                <Award className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-emerald-400">
                {evalResult.pass_at_1 !== null && evalResult.pass_at_1 !== undefined
                  ? `${evalResult.pass_at_1.toFixed(1)}%`
                  : 'N/A'}
              </div>
              <p className="text-[11px] text-slate-500">First-attempt pass rate on HumanEval</p>
            </div>

            {/* pass@5 */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span className="font-medium">pass@5 Accuracy</span>
                <CheckCircle2 className="h-4 w-4 text-indigo-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-indigo-400">
                {evalResult.pass_at_5 !== null && evalResult.pass_at_5 !== undefined
                  ? `${evalResult.pass_at_5.toFixed(1)}%`
                  : 'N/A'}
              </div>
              <p className="text-[11px] text-slate-500">Autonomous repair cumulative success</p>
            </div>

            {/* Average attempts */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span className="font-medium">Average Attempts</span>
                <Layers className="h-4 w-4 text-amber-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-slate-100">
                {evalResult.avg_attempts !== null && evalResult.avg_attempts !== undefined
                  ? evalResult.avg_attempts.toFixed(2)
                  : '—'}
              </div>
              <p className="text-[11px] text-slate-500">Attempts per solved problem</p>
            </div>

            {/* Average latency */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span className="font-medium">Average Latency</span>
                <Clock className="h-4 w-4 text-sky-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-slate-100">
                {evalResult.avg_latency_ms !== null && evalResult.avg_latency_ms !== undefined
                  ? `${evalResult.avg_latency_ms.toFixed(0)}ms`
                  : '—'}
              </div>
              <p className="text-[11px] text-slate-500">Sandbox execution time per attempt</p>
            </div>
          </div>

          {/* Benchmark Run Metadata Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Activity className="h-4 w-4 text-indigo-400" />
              <span>Latest Evaluation Summary</span>
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono pt-1">
              <div>
                <span className="text-slate-500 block text-[10px] uppercase">Benchmark</span>
                <span className="text-slate-200 font-medium">{evalResult.benchmark_name}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase">Problems Tested</span>
                <span className="text-slate-200 font-medium">
                  {evalResult.total_problems ?? '0'} problems
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase">Eval ID</span>
                <span className="text-slate-200 font-medium truncate block" title={evalResult.eval_id}>
                  {evalResult.eval_id}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase">Executed</span>
                <span className="text-slate-200 font-medium">
                  {evalResult.run_at ? new Date(evalResult.run_at).toLocaleString() : 'Recent'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
