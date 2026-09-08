import { useState } from 'react'
import {
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Cpu,
  FileCode,
  ShieldCheck,
  Terminal,
  XCircle,
  Zap,
} from 'lucide-react'
import type { AttemptOut } from '../api/types'

interface AttemptCardProps {
  attempt: AttemptOut
  defaultExpanded?: boolean
}

export default function AttemptCard({ attempt, defaultExpanded = true }: AttemptCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'code' | 'output' | 'reviews'>('code')

  const copyCode = () => {
    navigator.clipboard.writeText(attempt.generated_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasReviews = Boolean(
    attempt.generated_tests ||
      attempt.performance_notes ||
      attempt.security_audit ||
      attempt.critique_confidence !== null
  )

  return (
    <div
      className={`border rounded transition-all duration-150 overflow-hidden bg-surface ${
        attempt.success
          ? 'border-status-success/40'
          : 'border-border'
      }`}
    >
      {/* Card Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="px-4 py-3 bg-surface flex items-center justify-between cursor-pointer hover:bg-canvas select-none border-b border-border"
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="text-ink-secondary hover:text-ink transition-colors p-0.5"
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>

          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-ink">
              Attempt #{attempt.attempt_number}
            </span>
            {attempt.success ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-xs font-medium bg-status-success-subtle text-status-success border border-status-success/30">
                <CheckCircle2 className="h-3 w-3" />
                Passed Sandbox
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-xs font-medium bg-status-danger-subtle text-status-danger border border-status-danger/30">
                <XCircle className="h-3 w-3" />
                Execution Failed
              </span>
            )}
          </div>
        </div>

        {/* Telemetry metadata */}
        <div className="flex items-center gap-2 text-xs font-mono">
          {attempt.exit_code !== null && attempt.exit_code !== undefined && (
            <span
              className={`px-1.5 py-0.5 rounded-[2px] border ${
                attempt.exit_code === 0
                  ? 'bg-status-success-subtle border-status-success/30 text-status-success'
                  : 'bg-status-danger-subtle border-status-danger/30 text-status-danger'
              }`}
            >
              exit: {attempt.exit_code}
            </span>
          )}

          {attempt.latency_ms !== null && attempt.latency_ms !== undefined && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-surface-sunken border border-border text-ink-secondary">
              <Clock className="h-3 w-3 text-ink-tertiary" />
              {attempt.latency_ms}ms
            </span>
          )}
        </div>
      </div>

      {/* Card Body */}
      {expanded && (
        <div className="p-4 space-y-3 bg-surface">
          {/* Tabs */}
          <div className="flex items-center justify-between border-b border-border pb-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveTab('code')}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-[2px] transition-colors ${
                  activeTab === 'code'
                    ? 'bg-accent-subtle text-accent border border-accent/30'
                    : 'text-ink-secondary hover:text-ink hover:bg-canvas'
                }`}
              >
                <FileCode className="h-3.5 w-3.5" />
                <span>Generated Code</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('output')}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-[2px] transition-colors ${
                  activeTab === 'output'
                    ? 'bg-accent-subtle text-accent border border-accent/30'
                    : 'text-ink-secondary hover:text-ink hover:bg-canvas'
                }`}
              >
                <Terminal className="h-3.5 w-3.5" />
                <span>Stdout / Stderr</span>
              </button>

              {hasReviews && (
                <button
                  type="button"
                  onClick={() => setActiveTab('reviews')}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-[2px] transition-colors ${
                    activeTab === 'reviews'
                      ? 'bg-accent-subtle text-accent border border-accent/30'
                      : 'text-ink-secondary hover:text-ink hover:bg-canvas'
                  }`}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Agent Reviews</span>
                  {attempt.quality_overall_score && (
                    <span className="font-mono text-[10px] px-1 rounded bg-accent/15 text-accent font-bold">
                      {attempt.quality_overall_score.toFixed(1)}
                    </span>
                  )}
                </button>
              )}
            </div>

            {activeTab === 'code' && (
              <button
                type="button"
                onClick={copyCode}
                className="inline-flex items-center gap-1 text-xs text-ink-secondary hover:text-ink transition-colors px-2 py-0.5 rounded border border-border bg-surface hover:bg-canvas cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-status-success" />
                    <span className="text-status-success">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            )}
          </div>

          {/* Tab Content */}
          {activeTab === 'code' && (
            <div className="relative">
              <pre className="p-3.5 rounded-[2px] bg-surface-sunken border border-border text-xs font-mono text-ink overflow-x-auto leading-relaxed max-h-96">
                <code>{attempt.generated_code}</code>
              </pre>
            </div>
          )}

          {activeTab === 'output' && (
            <div className="space-y-2">
              {attempt.stdout && (
                <div>
                  <div className="text-[11px] font-mono text-status-success mb-1 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Standard Output</span>
                  </div>
                  <pre className="p-3 rounded-[2px] bg-surface-sunken border border-border text-xs font-mono text-ink overflow-x-auto whitespace-pre-wrap max-h-60">
                    {attempt.stdout}
                  </pre>
                </div>
              )}

              {attempt.stderr && (
                <div>
                  <div className="text-[11px] font-mono text-status-danger mb-1 flex items-center gap-1">
                    <XCircle className="h-3 w-3" />
                    <span>Standard Error</span>
                  </div>
                  <pre className="p-3 rounded-[2px] bg-surface-sunken border border-status-danger/30 text-xs font-mono text-status-danger overflow-x-auto whitespace-pre-wrap max-h-60 border-t-2 border-t-status-danger">
                    {attempt.stderr}
                  </pre>
                </div>
              )}

              {!attempt.stdout && !attempt.stderr && (
                <div className="p-4 text-center text-xs text-ink-tertiary bg-surface-sunken rounded-[2px] border border-border">
                  No terminal output recorded for this attempt.
                </div>
              )}
            </div>
          )}

          {activeTab === 'reviews' && (
            <div className="space-y-3">
              {/* Critique Reasoning */}
              {attempt.critique_confidence !== null && attempt.critique_confidence !== undefined && (
                <div className="p-3 rounded-[2px] bg-surface-sunken border border-border space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-ink flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5 text-accent" />
                      Critique Assessment
                    </span>
                    <span className="font-mono text-xs text-ink-secondary">
                      Confidence: {(attempt.critique_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-ink-secondary leading-relaxed max-w-[75ch]">
                    {attempt.critique_reasoning || 'No critique reasoning provided.'}
                  </p>
                </div>
              )}

              {/* Unit Tests */}
              {attempt.generated_tests && (
                <div className="p-3 rounded-[2px] bg-surface-sunken border border-border space-y-1.5">
                  <div className="text-xs font-semibold text-ink flex items-center gap-1.5">
                    <Zap className="h-3.5 w-3.5 text-status-warning" />
                    Synthesized Unit Tests
                  </div>
                  <pre className="p-2.5 rounded-[2px] bg-surface border border-border text-[11px] font-mono text-ink overflow-x-auto max-h-48">
                    {attempt.generated_tests}
                  </pre>
                </div>
              )}

              {/* Performance Analysis */}
              {attempt.performance_notes && (
                <div className="p-3 rounded-[2px] bg-surface-sunken border border-border space-y-1">
                  <div className="text-xs font-semibold text-ink flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-accent" />
                    Performance & Complexity
                  </div>
                  <p className="text-xs text-ink-secondary leading-relaxed max-w-[75ch]">
                    {attempt.performance_notes}
                  </p>
                </div>
              )}

              {/* Security Audit */}
              {attempt.security_audit && (
                <div className="p-3 rounded-[2px] bg-surface-sunken border border-border space-y-1">
                  <div className="text-xs font-semibold text-ink flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-status-success" />
                    Static Security Audit
                  </div>
                  <p className="text-xs text-ink-secondary leading-relaxed max-w-[75ch]">
                    {attempt.security_audit}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
