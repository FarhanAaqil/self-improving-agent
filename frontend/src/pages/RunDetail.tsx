import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ExternalLink,
  GitPullRequest,
  Layers,
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
      <div className="p-16 border border-border rounded bg-surface flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <div className="text-xs text-ink-secondary font-mono">Loading run detail for {runId}...</div>
      </div>
    )
  }

  if (isError || !run) {
    return (
      <div className="space-y-4">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs text-ink-secondary hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>
        <div className="p-6 rounded bg-status-danger-subtle border border-status-danger/30 text-status-danger space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="h-5 w-5" />
            <span>Run Not Found</span>
          </div>
          <div className="text-xs font-mono">
            {error instanceof Error ? error.message : `No records found in database for run '${runId}'.`}
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
      name: 'Generate',
      label: 'Synthesis',
      state: 'passed',
    },
    {
      id: 'critique',
      name: 'Critique',
      label: 'Confidence review',
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
      name: 'Test',
      label: 'Unit tests',
      state: latestAttempt?.generated_tests ? 'passed' : !isSuccess ? 'failed' : 'pending',
    },
    {
      id: 'performance',
      name: 'Performance',
      label: 'Complexity notes',
      state: latestAttempt?.performance_notes ? 'passed' : 'pending',
    },
    {
      id: 'security',
      name: 'Security Audit',
      label: 'AST analysis',
      state: latestAttempt?.security_audit ? 'passed' : 'pending',
    },
    {
      id: 'docs',
      name: 'Document',
      label: 'Docstrings & types',
      state: isSuccess ? 'passed' : 'pending',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Top navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 text-xs text-ink-secondary hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>

        <div className="flex items-center gap-2">
          {health?.github_configured && (
            <button
              type="button"
              onClick={handleOpenPr}
              disabled={isOpeningPr || (!passingAttempt && !latestAttempt)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-status-success hover:bg-status-success/90 text-xs font-medium text-white transition-colors cursor-pointer disabled:opacity-50"
              title="Open a Pull Request with the verified solution"
            >
              {isOpeningPr ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <GitPullRequest className="h-3.5 w-3.5" />
              )}
              <span>{isOpeningPr ? 'Opening PR...' : 'Open PR'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={downloadCode}
            disabled={!passingAttempt && !latestAttempt}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent hover:bg-accent-hover text-xs font-medium text-white transition-colors cursor-pointer disabled:opacity-50"
            title="Download generated Python code"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Download .py</span>
          </button>

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface hover:bg-canvas border border-border text-xs font-medium text-ink transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin text-accent' : 'text-ink-tertiary'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* PR Status Notification */}
      {prResult && (
        <div
          className={`p-4 rounded border text-xs flex items-center justify-between gap-3 ${
            prResult.status === 'success'
              ? 'bg-status-success-subtle border-status-success/30 text-status-success'
              : prResult.status === 'skipped'
              ? 'bg-status-warning-subtle border-status-warning/30 text-status-warning'
              : 'bg-status-danger-subtle border-status-danger/30 text-status-danger'
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
              className="inline-flex items-center gap-1 font-semibold underline hover:opacity-80 shrink-0"
            >
              <span>View PR on GitHub</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}

      {/* Pipeline Stepper at top */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-ink-secondary">Pipeline execution state:</div>
        <PipelineStepper steps={pipelineSteps} />
      </div>

      {/* Run Summary Card */}
      <div className="bg-surface border border-border rounded p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded bg-surface-sunken border border-border flex items-center justify-center text-accent">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-base font-semibold text-ink">{run.run_id}</span>
                <StatusBadge status={run.final_status} />
              </div>
              <div className="text-xs text-ink-secondary font-mono mt-0.5">
                Created: {run.created_at ? new Date(run.created_at).toLocaleString() : 'Unknown'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="px-3 py-1.5 rounded bg-surface-sunken border border-border text-center">
              <span className="text-ink-tertiary block text-[10px]">ATTEMPTS</span>
              <span className="text-ink font-semibold">{run.total_attempts}</span>
            </div>
            <div className="px-3 py-1.5 rounded bg-surface-sunken border border-border text-center">
              <span className="text-ink-tertiary block text-[10px]">TOTAL LATENCY</span>
              <span className="text-ink font-semibold">{totalLatency}ms</span>
            </div>
          </div>
        </div>

        {/* Task description */}
        <div>
          <div className="text-xs font-medium text-ink-secondary mb-1">
            Task prompt
          </div>
          <p className="text-xs text-ink font-mono bg-surface-sunken p-3 rounded border border-border leading-relaxed whitespace-pre-wrap">
            {run.task_description}
          </p>
        </div>
      </div>

      {/* Critique Reasoning Banner */}
      {latestAttempt?.critique_confidence !== null &&
        latestAttempt?.critique_confidence !== undefined && (
          <div
            className={`p-4 rounded border flex items-start gap-3.5 text-xs bg-surface ${
              isEarlyStopped
                ? 'border-status-warning/40 bg-status-warning-subtle/30'
                : 'border-border'
            }`}
          >
            <Scale className="h-4 w-4 shrink-0 text-accent mt-0.5" />
            <div className="space-y-1 flex-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">
                  Critique confidence analysis
                </span>
                <span className="font-mono px-2 py-0.5 rounded bg-surface-sunken border border-border text-ink-secondary">
                  Confidence: {(latestAttempt.critique_confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-ink-secondary leading-relaxed font-sans max-w-[75ch]">
                {isEarlyStopped
                  ? 'Early-stop triggered: The Critique agent assessed confidence below 0.3 threshold, terminating the repair loop early to avoid wasteful token consumption on intractable errors.'
                  : `Critique score ${(latestAttempt.critique_confidence * 100).toFixed(0)}% exceeds the 0.3 threshold. Code passed semantic inspection.`}
              </p>
            </div>
          </div>
        )}

      {/* Code diff view between attempts */}
      {run.attempts.length >= 2 && <CodeDiffView attempts={run.attempts} />}

      {/* Attempts Timeline */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink flex items-center gap-2">
            <Terminal className="h-4 w-4 text-accent" />
            <span>Attempt timeline ({run.attempts.length})</span>
          </h2>
          {passingAttempt && (
            <span className="text-xs text-status-success font-mono">
              Passed on Attempt #{passingAttempt.attempt_number}
            </span>
          )}
        </div>

        {run.attempts.length === 0 ? (
          <div className="p-8 border border-border rounded bg-surface text-center text-xs text-ink-tertiary">
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
