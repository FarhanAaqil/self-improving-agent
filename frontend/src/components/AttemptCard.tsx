import { useState } from 'react'
import {
  AlertOctagon,
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
      className={`border rounded-xl transition-all duration-150 overflow-hidden ${
        attempt.success
          ? 'border-emerald-500/30 bg-slate-900/70 shadow-sm shadow-emerald-500/5'
          : 'border-slate-800 bg-slate-900/40'
      }`}
    >
      {/* Card Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="px-4 py-3 bg-slate-900/90 flex items-center justify-between cursor-pointer hover:bg-slate-850 select-none border-b border-slate-800/80"
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="text-slate-400 hover:text-slate-200 transition-colors p-0.5"
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>

          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-slate-100">
              Attempt #{attempt.attempt_number}
            </span>
            {attempt.success ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                <CheckCircle2 className="h-3 w-3" />
                Passed Sandbox
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30">
                <XCircle className="h-3 w-3" />
                Execution Failed
              </span>
            )}
          </div>
        </div>

        {/* Telemetry metadata chips */}
        <div className="flex items-center gap-2 text-xs font-mono">
          {attempt.exit_code !== null && attempt.exit_code !== undefined && (
            <span
              className={`px-1.5 py-0.5 rounded border ${
                attempt.exit_code === 0
                  ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-400'
                  : 'bg-rose-950/40 border-rose-800/60 text-rose-400'
              }`}
            >
              exit: {attempt.exit_code}
            </span>
          )}

          {attempt.latency_ms !== null && attempt.latency_ms !== undefined && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700/80 text-slate-300">
              <Clock className="h-3 w-3 text-slate-400" />
              {attempt.latency_ms}ms
            </span>
          )}

          {attempt.model_name && (
            <span className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-400">
              <Cpu className="h-3 w-3 text-slate-500" />
              {attempt.model_name.replace('llama-', '')}
            </span>
          )}
        </div>
      </div>

      {/* Card Body */}
      {expanded && (
        <div>
          {/* Section Tabs */}
          <div className="flex border-b border-slate-800 bg-slate-950/60 px-4 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('code')}
              className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
                activeTab === 'code'
                  ? 'border-indigo-500 text-indigo-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileCode className="h-3.5 w-3.5" />
              Generated Code
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('output')}
              className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
                activeTab === 'output'
                  ? 'border-indigo-500 text-indigo-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="h-3.5 w-3.5" />
              Sandbox Output
              {(attempt.stderr || !attempt.success) && (
                <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
              )}
            </button>
            {hasReviews && (
              <button
                type="button"
                onClick={() => setActiveTab('reviews')}
                className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
                  activeTab === 'reviews'
                    ? 'border-indigo-500 text-indigo-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                Review & Analysis
              </button>
            )}
          </div>

          {/* Tab 1: Code */}
          {activeTab === 'code' && (
            <div className="relative group">
              <button
                type="button"
                onClick={copyCode}
                className="absolute top-2.5 right-2.5 z-10 px-2 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1 border border-slate-700 transition-all opacity-80 group-hover:opacity-100 cursor-pointer"
                title="Copy code"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
              <pre className="p-4 bg-slate-950 font-mono text-xs text-slate-200 overflow-x-auto leading-relaxed selection:bg-indigo-500/30">
                <code>{attempt.generated_code}</code>
              </pre>
            </div>
          )}

          {/* Tab 2: Output */}
          {activeTab === 'output' && (
            <div className="p-4 bg-slate-950/95 font-mono text-xs space-y-3">
              {attempt.stdout && (
                <div>
                  <div className="text-[11px] font-semibold text-emerald-400 mb-1 flex items-center gap-1">
                    <Terminal className="h-3 w-3" /> Standard Output:
                  </div>
                  <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 overflow-x-auto whitespace-pre-wrap">
                    {attempt.stdout}
                  </pre>
                </div>
              )}

              {attempt.stderr && (
                <div>
                  <div className="text-[11px] font-semibold text-rose-400 mb-1 flex items-center gap-1">
                    <AlertOctagon className="h-3 w-3" /> Standard Error / Traceback:
                  </div>
                  <pre className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/40 text-rose-200 overflow-x-auto whitespace-pre-wrap">
                    {attempt.stderr}
                  </pre>
                </div>
              )}

              {!attempt.stdout && !attempt.stderr && (
                <div className="text-slate-500 italic py-2">No console output produced by process.</div>
              )}
            </div>
          )}

          {/* Tab 3: Reviews */}
          {activeTab === 'reviews' && hasReviews && (
            <div className="p-4 bg-slate-950 space-y-4 text-xs">
              {attempt.critique_confidence !== null && attempt.critique_confidence !== undefined && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/70 border border-slate-800">
                  <span className="text-slate-300 font-medium">Critique Confidence:</span>
                  <span className="font-mono font-semibold text-indigo-400">
                    {(attempt.critique_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}

              {attempt.generated_tests && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Synthesized Unit Tests
                  </span>
                  <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap">
                    {attempt.generated_tests}
                  </pre>
                </div>
              )}

              {attempt.performance_notes && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5 text-amber-400" /> Performance Analysis
                  </span>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 whitespace-pre-wrap">
                    {attempt.performance_notes}
                  </div>
                </div>
              )}

              {attempt.security_audit && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center gap-1">
                    <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" /> Code Security Audit
                  </span>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 whitespace-pre-wrap">
                    {attempt.security_audit}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
