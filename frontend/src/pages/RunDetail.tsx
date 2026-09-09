import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ExternalLink,
  GitPullRequest,
  Loader2,
  RefreshCw,
  Scale,
  Terminal,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getHealth, getRun, openRunPr } from '../api/client'
import type { PrResponse, RunOut } from '../api/types'
import AttemptCard from '../components/AttemptCard'
import CodeDiffView from '../components/CodeDiffView'
import PipelineStepper, { type PipelineStep } from '../components/PipelineStepper'
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

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  })

  const [isOpeningPr, setIsOpeningPr] = useState(false)
  const [prResult, setPrResult] = useState<PrResponse | null>(null)

  const handleOpenPr = async () => {
    if (!run) return
    setIsOpeningPr(true)
    setPrResult(null)
    try {
      const res = await openRunPr(run.run_id)
      setPrResult(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to open PR'
      setPrResult({ status: 'error', error: msg })
    } finally {
      setIsOpeningPr(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-16 border border-border bg-surface flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <div className="text-xs text-ink-secondary font-mono">loading ledger for {runId}...</div>
      </div>
    )
  }

  if (isError || !run) {
    return (
      <div className="space-y-4">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-ink-secondary hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>← back to run history</span>
        </Link>
        <div className="p-6 bg-status-danger-subtle border border-status-danger/30 text-status-danger space-y-2 font-mono">
          <div className="flex items-center gap-2 font-bold">
            <AlertCircle className="h-5 w-5" />
            <span>run record not found</span>
          </div>
          <div className="text-xs">
            {error instanceof Error ? error.message : `No records found in SQLite database for run '${runId}'.`}
          </div>
        </div>
      </div>
    )
  }

  const totalLatency = run.attempts.reduce((sum, a) => sum + (a.latency_ms || 0), 0)
  const passingAttempt = run.attempts.find((a) => a.success)
  const latestAttempt = run.attempts[run.attempts.length - 1]
  const isSuccess = run.final_status === 'success'

  // Early-stop detection
  const isEarlyStopped =
    latestAttempt &&
    latestAttempt.critique_confidence !== null &&
    latestAttempt.critique_confidence !== undefined &&
    latestAttempt.critique_confidence < 0.3 &&
    !latestAttempt.success

  const downloadCode = () => {
    const targetCode = passingAttempt?.generated_code || latestAttempt?.generated_code
    if (!targetCode) return
    const blob = new Blob([targetCode], { type: 'text/x-python;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${run.run_id}_solution.py`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Pipeline stepper state
  const pipelineSteps: PipelineStep[] = [
    {
      id: 'generate',
      name: 'generate',
      label: 'synthesis',
      state: 'passed',
    },
    {
      id: 'critique',
      name: 'critique',
      label: 'confidence review',
      state: isEarlyStopped
        ? 'failed'
        : latestAttempt?.critique_confidence !== null && latestAttempt?.critique_confidence !== undefined
        ? 'passed'
        : isSuccess
        ? 'passed'
        : 'pending',
    },
    {
      id: 'test',
      name: 'test',
      label: 'cgroup sandbox',
      state: latestAttempt?.generated_tests ? 'passed' : !isSuccess ? 'failed' : 'pending',
    },
    {
      id: 'performance',
      name: 'performance',
      label: 'complexity audit',
      state: latestAttempt?.performance_notes ? 'passed' : 'pending',
    },
    {
      id: 'security',
      name: 'security',
      label: 'ast verification',
      state: latestAttempt?.security_audit ? 'passed' : 'pending',
    },
    {
      id: 'docs',
      name: 'document',
      label: 'docstrings & types',
      state: isSuccess ? 'passed' : 'pending',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Top navigation & action bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-ink-secondary hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>← back to run history</span>
        </Link>

        <div className="flex items-center gap-2.5">
          {health?.github_configured && (
            <button
              type="button"
              onClick={handleOpenPr}
              disabled={isOpeningPr || (!passingAttempt && !latestAttempt)}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-status-success hover:bg-status-success/90 text-xs font-mono font-bold text-white uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-50"
              title="Open a Pull Request with the verified solution"
            >
              {isOpeningPr ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <GitPullRequest className="h-3.5 w-3.5" />
              )}
              <span>{isOpeningPr ? 'opening pr...' : 'open pr'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={downloadCode}
            disabled={!passingAttempt && !latestAttempt}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-accent hover:bg-accent-hover text-xs font-mono font-bold text-white uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-50"
            title="Download generated Python code"
          >
            <Download className="h-3.5 w-3.5" />
            <span>download .py</span>
          </button>

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-surface hover:bg-surface-sunken border border-border-strong text-xs font-mono text-ink transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-accent' : 'text-ink-tertiary'}`} />
            <span>refresh</span>
          </button>
        </div>
      </div>

      {/* PR Status Notification */}
      {prResult && (
        <div
          className={`p-4 border text-xs flex items-center justify-between gap-3 font-mono ${
            prResult.status === 'success'
              ? 'bg-status-success-subtle border-status-success/40 text-status-success'
              : prResult.status === 'skipped'
              ? 'bg-status-warning-subtle border-status-warning/40 text-status-warning'
              : 'bg-status-danger-subtle border-status-danger/40 text-status-danger'
          }`}
        >
          <div className="flex items-center gap-2">
            {prResult.status === 'success' ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0" />
            )}
            <span>
              {prResult.status === 'success'
                ? `Pull Request #${prResult.pr_number} opened on branch ${prResult.branch}!`
                : prResult.error || prResult.reason || 'GitHub action finished.'}
            </span>
          </div>
          {prResult.pr_url && (
            <a
              href={prResult.pr_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-bold underline hover:opacity-80 shrink-0 text-cyan"
            >
              <span>view pr on github</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}

      {/* Full-size Pipeline Stepper with Reticle Corner Brackets */}
      <div className="space-y-2">
        <div className="text-xs font-mono font-bold uppercase tracking-wider text-ink-secondary">
          pipeline verification sequence:
        </div>
        <PipelineStepper steps={pipelineSteps} />
      </div>

      {/* Run Summary Instrument Panel */}
      <div className="bg-surface border border-border p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="relative shrink-0 h-10 w-10 bg-[#10241C] border border-accent/40 flex items-center justify-center shadow-xs">
              <img src="/logo-square.jpg" alt="CODE_AGENT" className="h-9 w-9 object-cover" />
              <span className="absolute top-0 right-0 h-1.5 w-1.5 bg-accent" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-base font-bold text-ink">{run.run_id}</span>
                <StatusBadge status={run.final_status} />
              </div>
              <div className="text-xs text-ink-secondary font-mono mt-0.5">
                timestamp: {run.created_at ? new Date(run.created_at).toLocaleString() : 'Unknown'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="px-3 py-1.5 bg-surface-sunken border border-border text-center">
              <span className="text-ink-tertiary block text-[10px] uppercase">attempts</span>
              <span className="text-ink font-bold">{run.total_attempts}</span>
            </div>
            <div className="px-3 py-1.5 bg-surface-sunken border border-border text-center">
              <span className="text-ink-tertiary block text-[10px] uppercase">total latency</span>
              <span className="text-ink font-bold">{totalLatency}ms</span>
            </div>
          </div>
        </div>

        {/* Task description */}
        <div>
          <div className="text-xs font-mono font-bold uppercase tracking-wider text-ink-secondary mb-1.5">
            task specification
          </div>
          <p className="text-xs text-ink font-mono bg-surface-sunken p-3 border border-border leading-relaxed whitespace-pre-wrap">
            {run.task_description}
          </p>
        </div>
      </div>

      {/* Critique Reasoning Banner */}
      {latestAttempt?.critique_confidence !== null &&
        latestAttempt?.critique_confidence !== undefined && (
          <div
            className={`p-4 border flex items-start gap-3.5 text-xs font-mono bg-surface ${
              isEarlyStopped
                ? 'border-status-warning/50 bg-status-warning-subtle/30'
                : 'border-border'
            }`}
          >
            <Scale className="h-4 w-4 shrink-0 text-accent mt-0.5" />
            <div className="space-y-1 flex-1 font-sans">
              <div className="flex items-center justify-between font-mono">
                <span className="font-bold text-ink text-xs uppercase tracking-wider">
                  critique confidence analysis
                </span>
                <span className="px-2 py-0.5 bg-surface-sunken border border-border text-ink-secondary text-xs">
                  confidence: {(latestAttempt.critique_confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-ink-secondary leading-relaxed max-w-[75ch] text-xs pt-1">
                {isEarlyStopped
                  ? 'Early-stop triggered: The Critique agent assessed confidence below 0.3 threshold, terminating the repair loop early to avoid wasteful token consumption on intractable errors.'
                  : `Critique score ${(latestAttempt.critique_confidence * 100).toFixed(0)}% exceeds the 0.3 threshold. Code passed semantic inspection.`}
              </p>
            </div>
          </div>
        )}

      {/* Code diff view between attempts */}
      {run.attempts.length >= 2 && <CodeDiffView attempts={run.attempts} />}

      {/* Attempts Timeline with Gutter Indexing */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-2">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-ink flex items-center gap-2">
            <Terminal className="h-4 w-4 text-accent" />
            <span>attempt timeline ({run.attempts.length})</span>
          </h2>
          {passingAttempt && (
            <span className="text-xs text-status-success font-mono font-bold">
              [✓ passed on attempt #{passingAttempt.attempt_number}]
            </span>
          )}
        </div>

        {run.attempts.length === 0 ? (
          <div className="p-8 border border-border bg-surface text-center text-xs font-mono text-ink-tertiary">
            no execution attempts recorded for this run.
          </div>
        ) : (
          <div className="space-y-4">
            {run.attempts.map((attempt) => (
              <div key={attempt.attempt_id ?? attempt.attempt_number} className="relative pl-6">
                {/* Attempt index stamped in gutter connection */}
                <div className="absolute left-0 top-3 font-mono text-xs font-bold text-accent select-none">
                  0{attempt.attempt_number}
                </div>
                <AttemptCard
                  attempt={attempt}
                  defaultExpanded={attempt.attempt_number === run.attempts.length}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
