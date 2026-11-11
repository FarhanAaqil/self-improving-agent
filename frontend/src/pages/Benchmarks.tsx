import { useMutation, useQuery } from '@tanstack/react-query'
import { BarChart3, Play, X } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { getAgentBenchmarks, getEvalHistory, getEvalStatus, getLatestEval, triggerEval } from '../api/client'
import type { BenchmarkResult } from '../api/types'
import AgentBenchmarkPanel from '../components/AgentBenchmarkPanel'

// The charts library is ~300KB; only fetch it when there is a history worth drawing
const BenchmarkHistoryChart = lazy(() => import('../components/BenchmarkHistoryChart'))
import { Chip, EmptyState, ErrorNote, Meter, PageHeader, Panel, Skeleton } from '../components/ui'

// Ordinal teal: solved on attempt 1 is the strongest mark (validated light/dark ramps)
const ATTEMPT_FILL = ['bg-[#0B5E66] dark:bg-[#8FDDE3]', 'bg-[#0E7C86] dark:bg-[#3FB8C2]', 'bg-[#5FAFB6] dark:bg-[#1F7F87]']

function Bar({ label, value, ci, note }: { label: string; value: number; ci?: [number, number]; note?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-ink">{label}</span>
        <span className="font-mono text-sm font-bold tabular-nums text-ink">{value.toFixed(1)}%</span>
      </div>
      <div className="relative mt-1.5 h-3 bg-surface-sunken">
        <div className="h-full bg-chart-1" style={{ width: `${value}%` }} />
        {ci && (
          <div
            className="absolute top-1/2 h-px -translate-y-1/2 bg-ink"
            style={{ left: `${ci[0]}%`, width: `${Math.max(0.5, ci[1] - ci[0])}%` }}
            aria-hidden
          />
        )}
      </div>
      <div className="mt-1 font-mono text-[10px] text-ink-muted">
        {ci ? `95% CI ${ci[0]}–${ci[1]}%` : ''}
        {note ? `${ci ? ' · ' : ''}${note}` : ''}
      </div>
    </div>
  )
}

function ProblemGrid({ result }: { result: BenchmarkResult }) {
  if (!result.results?.length) return null
  return (
    <Panel title="every problem" actions={<span className="font-mono text-[10px] text-ink-muted">{result.results.length} cells</span>}>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(28px,1fr))] gap-[2px]" aria-label="Per-problem results">
        {result.results.map((r) => {
          const fill = r.passed_at_attempt ? ATTEMPT_FILL[Math.min(r.passed_at_attempt, 3) - 1] : 'bg-status-danger-subtle'
          const label = `${r.problem_id}: ${r.passed_at_attempt ? `solved on attempt ${r.passed_at_attempt}` : 'unsolved'}; baseline ${r.baseline_passed ? 'passed' : 'failed'}`
          return (
            <li key={r.problem_id} title={label} aria-label={label} className={`flex aspect-square items-center justify-center ${fill}`}>
              {!r.passed_at_attempt && <X className="h-3 w-3 text-status-danger" aria-hidden />}
              {r.passed_at_attempt && !r.baseline_passed && <span className="h-1.5 w-1.5 bg-accent" aria-hidden />}
            </li>
          )
        })}
      </ul>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-ink-secondary">
        {['attempt 1', 'attempt 2', 'attempt 3+'].map((l, i) => (
          <span key={l} className="flex items-center gap-1.5"><span className={`h-2.5 w-2.5 ${ATTEMPT_FILL[i]}`} aria-hidden />{l}</span>
        ))}
        <span className="flex items-center gap-1.5"><X className="h-2.5 w-2.5 text-status-danger" aria-hidden />unsolved</span>
        <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 bg-accent" aria-hidden />repair beat the baseline</span>
      </div>
    </Panel>
  )
}

export default function Benchmarks() {
  const [evalId, setEvalId] = useState<string | null>(null)
  const [size, setSize] = useState(10)

  const latest = useQuery({ queryKey: ['eval-latest'], queryFn: getLatestEval })
  // Same query the panel uses (shared cache): wait for both so panels don't push each other down
  const agentRuns = useQuery({ queryKey: ['agent-benchmarks'], queryFn: getAgentBenchmarks })
  const settling = latest.isLoading || agentRuns.isLoading
  const history = useQuery({ queryKey: ['eval-history'], queryFn: getEvalHistory })
  const status = useQuery({
    queryKey: ['eval-status', evalId],
    queryFn: () => getEvalStatus(evalId!),
    enabled: Boolean(evalId),
    refetchInterval: (q) => (q.state.data?.status === 'running' || !q.state.data ? 2000 : false),
  })
  const start = useMutation({ mutationFn: () => triggerEval({ benchmark: 'humaneval', subset_size: size }), onSuccess: (r) => setEvalId(r.eval_id) })

  const raw = latest.data?.raw as BenchmarkResult | undefined
  const result = raw && raw.agent && raw.baseline ? raw : undefined
  const points = [...(history.data?.items ?? [])]
    .filter((h) => h.agent && h.baseline)
    .reverse()
    .map((h) => ({ date: h.date, baseline: h.baseline.pass_at_1, agent: h.agent.solve_at_k }))

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="benchmarks"
        title="Measured, not claimed"
        lede="Official HumanEval problems with their original hidden tests, run in the sandbox. After a failure I only hear the error type, never the test, so I can't learn the answers."
        actions={
          <div className="flex items-center gap-2">
            <label className="font-mono text-[11px] text-ink-muted">
              <span className="sr-only">Problems</span>
              <select value={size} onChange={(e) => setSize(Number(e.target.value))} className="input w-auto py-1.5 text-xs">
                {[5, 10, 20, 40].map((n) => <option key={n} value={n}>{n} problems</option>)}
              </select>
            </label>
            <button type="button" className="btn-primary" disabled={start.isPending || status.data?.status === 'running'} onClick={() => start.mutate()}>
              <Play className="h-3.5 w-3.5" aria-hidden /> run benchmark
            </button>
          </div>
        }
      />

      {start.isError && <ErrorNote error={start.error} />}
      {status.data && (
        <Panel title={`benchmark ${status.data.eval_id}`} actions={<Chip tone={status.data.status === 'failed' ? 'danger' : status.data.status === 'done' ? 'success' : 'accent'}>{status.data.status}</Chip>}>
          <div className="flex items-center justify-between font-mono text-xs text-ink-secondary">
            <span>{status.data.done} / {status.data.total} problems</span>
            <span className="flex gap-1">
              {status.data.recent.map((r) => (
                <span key={r.id} title={r.id} className={`h-2.5 w-2.5 ${r.passed ? 'bg-status-success' : 'bg-status-danger'}`} aria-label={`${r.id} ${r.passed ? 'passed' : 'failed'}`} />
              ))}
            </span>
          </div>
          <div className="mt-2"><Meter value={status.data.total ? status.data.done / status.data.total : 0} label="Benchmark progress" /></div>
          {status.data.error && <p className="mt-2 text-xs text-status-danger">{status.data.error}</p>}
        </Panel>
      )}

      {settling ? <Skeleton className="h-[28rem]" /> : <AgentBenchmarkPanel />}

      {settling ? null : latest.isLoading ? (
        <Skeleton className="h-64" />
      ) : !result ? (
        <EmptyState icon={<BarChart3 className="h-8 w-8" />} title="No benchmark yet">
          Run one above, or from the command line with <code className="font-mono">python -m eval.benchmark</code>.
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
            <Panel title="latest result" actions={<Chip tone={result.sandboxed ? 'success' : 'danger'}>{result.sandboxed ? 'sandboxed' : 'not sandboxed'}</Chip>}>
              <p className="mb-4 font-mono text-[11px] text-ink-muted">
                {result.total_problems} {result.suite} problems · {result.model} · {result.date}
              </p>
              <div className="space-y-5">
                <Bar label="Single-shot baseline" value={result.baseline.pass_at_1} ci={result.baseline.ci95} note="no feedback" />
                <Bar label="Agent, first attempt" value={result.agent.pass_at_1} />
                <Bar label={`Agent, within ${result.agent.k} attempts`} value={result.agent.solve_at_k} ci={result.agent.ci95} note={`avg ${result.agent.avg_attempts} attempts`} />
              </div>
              <p className="mt-5 border-t border-border pt-3 text-sm text-ink-secondary">
                Repair changed the solve rate by{' '}
                <span className="font-mono font-bold text-ink">{result.repair_gain_pct >= 0 ? '+' : ''}{result.repair_gain_pct.toFixed(1)} pts</span>.
                {result.baseline.pass_at_1 >= 95 && ' The baseline is already at the ceiling, so this set cannot show a repair gain.'}
              </p>
            </Panel>
            <ProblemGrid result={result} />
          </div>

          {points.length >= 2 && (
            <Panel title="over time">
              <Suspense fallback={<Skeleton className="h-64" />}>
                <BenchmarkHistoryChart points={points} />
              </Suspense>
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
