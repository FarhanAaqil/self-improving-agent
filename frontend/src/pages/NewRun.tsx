import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  AlertCircle,
  Layers,
  Loader2,
  Play,
  Sliders,
  WifiOff,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { generateAndRepair, getHealth, getRun } from '../api/client'
import type { RunOut } from '../api/types'
import AttemptCard from '../components/AttemptCard'
import PipelineStepper, { type PipelineStep } from '../components/PipelineStepper'
import StatusBadge from '../components/StatusBadge'

const TEMPLATE_PROMPTS = [
  {
    title: 'LRU Cache',
    category: 'ALGO',
    prompt:
      'Write a complete LRUCache class in Python with get(key) and put(key, value) in O(1) time complexity using a doubly linked list and hashmap. Include self-tests asserting eviction order and capacity limits.',
  },
  {
    title: 'Parse Access Logs',
    category: 'REGEX',
    prompt:
      'Write a function parse_access_logs(logs) that parses web server log lines with regex, extracts client IP addresses, HTTP methods, and status codes, and returns a dictionary counting status codes per unique IP. Test with sample log strings.',
  },
  {
    title: 'Validate BST',
    category: 'DATA_STRUCT',
    prompt:
      'Write a function is_valid_bst(root) that checks whether a binary tree is a valid Binary Search Tree with strictly increasing in-order traversal values. Include test cases with valid and invalid trees.',
  },
  {
    title: 'Safe Path Traversal Guard',
    category: 'SECURITY',
    prompt:
      "Write a function safe_join(base_dir, user_path) that safely resolves an untrusted user path within base_dir and raises ValueError on directory traversal attempts (like '../'). Include test cases verifying traversal attacks are blocked.",
  },
]

export default function NewRun() {
  const [taskDescription, setTaskDescription] = useState('')
  const [model, setModel] = useState('llama-3.3-70b-versatile')
  const [maxAttempts, setMaxAttempts] = useState(3)
  const [skipAgents, setSkipAgents] = useState<string[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 20000,
  })
  const isApiOnline = health?.status === 'healthy'

  // Polling query: polls GET /runs/{run_id} while the agent is running
  const { data: polledRun } = useQuery<RunOut>({
    queryKey: ['run', activeRunId],
    queryFn: () => getRun(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const state = query.state.data
      if (state && ['success', 'failed', 'max_retries_exceeded'].includes(state.final_status)) {
        return false
      }
      return 1500
    },
  })

  // Mutation: triggers POST /generate-and-repair
  const runMutation = useMutation<RunOut, Error, { task: string }>({
    mutationFn: ({ task }) =>
      generateAndRepair({
        task_description: task,
        model,
        max_attempts: maxAttempts,
        skip_agents: skipAgents,
      }),
    onSuccess: (data) => {
      setActiveRunId(data.run_id)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (taskDescription.trim().length < 5) {
      setValidationError('task prompt requires at least 5 characters for validation.')
      return
    }
    setValidationError(null)
    runMutation.mutate({ task: taskDescription })
  }

  const handleSelectTemplate = (prompt: string) => {
    setTaskDescription(prompt)
    setValidationError(null)
  }

  const toggleSkipAgent = (agent: string) => {
    setSkipAgents((prev) =>
      prev.includes(agent) ? prev.filter((a) => a !== agent) : [...prev, agent]
    )
  }

  const isExecuting = runMutation.isPending || (polledRun?.final_status === 'running')
  const displayRun = polledRun || runMutation.data
  const latestAttempt = displayRun?.attempts[displayRun.attempts.length - 1]
  const isSuccess = displayRun?.final_status === 'success'
  const isComplete =
    displayRun?.final_status &&
    ['success', 'failed', 'max_retries_exceeded'].includes(displayRun.final_status)

  // Dynamic Pipeline Steps
  const pipelineSteps: PipelineStep[] = [
    {
      id: 'generate',
      name: 'generate',
      label: 'synthesis',
      state: isExecuting && (!displayRun || displayRun.attempts.length === 0)
        ? 'active'
        : displayRun && displayRun.attempts.length > 0
        ? 'passed'
        : 'pending',
    },
    {
      id: 'critique',
      name: 'critique',
      label: 'semantic confidence',
      state: isExecuting && latestAttempt && !latestAttempt.critique_confidence
        ? 'active'
        : latestAttempt?.critique_confidence !== null && latestAttempt?.critique_confidence !== undefined
        ? latestAttempt.critique_confidence < 0.3 && !latestAttempt.success
          ? 'failed'
          : 'passed'
        : isComplete && isSuccess
        ? 'passed'
        : 'pending',
    },
    {
      id: 'test',
      name: 'test',
      label: 'cgroup execution',
      state: isExecuting && latestAttempt?.generated_code && !latestAttempt.stdout && !latestAttempt.stderr
        ? 'active'
        : latestAttempt?.success
        ? 'passed'
        : latestAttempt && !latestAttempt.success
        ? 'failed'
        : 'pending',
    },
    {
      id: 'performance',
      name: 'performance',
      label: 'algorithmic audit',
      state: skipAgents.includes('performance')
        ? 'skipped'
        : latestAttempt?.performance_notes
        ? 'passed'
        : isComplete && isSuccess
        ? 'passed'
        : 'pending',
    },
    {
      id: 'security',
      name: 'security',
      label: 'ast verification',
      state: skipAgents.includes('security_audit')
        ? 'skipped'
        : latestAttempt?.security_audit
        ? 'passed'
        : isComplete && isSuccess
        ? 'passed'
        : 'pending',
    },
    {
      id: 'docs',
      name: 'document',
      label: 'docstrings & types',
      state: skipAgents.includes('docs')
        ? 'skipped'
        : isComplete && isSuccess
        ? 'passed'
        : 'pending',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="border-b border-border pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="relative shrink-0 h-10 w-10 bg-[#10241C] border border-accent/40 flex items-center justify-center shadow-xs">
            <img src="/logo-square.jpg" alt="CODE_AGENT" className="h-9 w-9 object-cover" />
            <span className="absolute top-0 right-0 h-1.5 w-1.5 bg-accent" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-mono font-bold tracking-tight text-ink">
                new run
              </h1>
              <span className="text-[10px] font-mono px-1.5 py-0.5 bg-surface-sunken border border-border text-ink-tertiary">
                AUTONOMOUS V1.0
              </span>
            </div>
            <p className="text-xs text-ink-secondary mt-0.5 font-sans">
              Interrogate and synthesize code in a locked-down container sandbox with automated critique.
            </p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 font-mono text-[11px] text-ink-tertiary">
          <span className="px-2 py-1 bg-surface border border-border text-ink-secondary flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 bg-status-success" />
            cgroup: isolated
          </span>
        </div>
      </div>

      {/* API Offline Warning */}
      {health && !isApiOnline && (
        <div className="flex items-center gap-3 p-3 bg-status-danger-subtle border border-status-danger/30 text-status-danger text-xs font-mono">
          <WifiOff className="h-4 w-4 shrink-0" />
          <span>Backend API is unreachable. Check that the FastAPI server is running on port 8000.</span>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-surface border border-border p-5 space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="task" className="text-xs font-mono font-bold uppercase tracking-wider text-ink">
                01 // task specification <span className="text-status-danger">*</span>
              </label>
              <span className="text-xs text-ink-tertiary font-mono">
                {taskDescription.length} chars (min 5)
              </span>
            </div>
            <textarea
              id="task"
              rows={4}
              value={taskDescription}
              onChange={(e) => {
                setTaskDescription(e.target.value)
                if (validationError && e.target.value.trim().length >= 5) {
                  setValidationError(null)
                }
              }}
              placeholder="e.g. Write a function parse_access_logs(logs) that parses web server log lines with regex, extracts client IP addresses, HTTP methods, and status codes..."
              className="w-full bg-surface-sunken border border-border p-3 text-xs text-ink placeholder-ink-tertiary focus:outline-none focus:border-accent focus:bg-surface transition-all font-mono"
            />
            {validationError && (
              <div className="flex items-center gap-1.5 text-xs font-mono text-status-danger mt-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{validationError}</span>
              </div>
            )}
          </div>

          {/* Template Quick-Picks as square outlined chips */}
          <div>
            <div className="text-xs font-mono text-ink-secondary mb-1.5">template quick-picks:</div>
            <div className="flex flex-wrap gap-2">
              {TEMPLATE_PROMPTS.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => handleSelectTemplate(item.prompt)}
                  className="px-2.5 py-1 text-xs text-ink-secondary hover:text-ink bg-surface-sunken hover:bg-canvas border border-border transition-colors cursor-pointer font-sans"
                >
                  <span className="font-mono text-[11px] text-accent mr-1.5 font-bold">[{item.category}]</span>
                  <span>{item.title}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Controls bar */}
          <div className="flex items-center justify-between pt-3 border-t border-border">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1.5 text-xs font-mono text-ink-secondary hover:text-ink transition-colors cursor-pointer"
            >
              <Sliders className="h-3.5 w-3.5" />
              <span>{showAdvanced ? '[-] hide settings' : '[+] runtime settings'}</span>
            </button>

            {/* Primary Action: Solid Orange Fill, Fully Square, Monospace Label */}
            <button
              type="submit"
              disabled={taskDescription.trim().length < 5 || isExecuting}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-mono font-bold uppercase tracking-wider transition-colors cursor-pointer"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>pipeline executing...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-white" />
                  <span>execute task [⏎]</span>
                </>
              )}
            </button>
          </div>

          {/* Runtime Settings Accordion */}
          {showAdvanced && (
            <div className="pt-4 border-t border-border grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div>
                <label className="block text-ink font-bold mb-1">inference model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-surface-sunken border border-border p-2 text-ink font-mono focus:outline-none focus:border-accent"
                >
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (recommended)</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (fast)</option>
                  <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b</option>
                  <option value="mixtral-8x7b-32768">mixtral-8x7b-32768</option>
                  <option value="gemma2-9b-it">gemma2-9b-it</option>
                </select>
              </div>

              <div>
                <label className="block text-ink font-bold mb-1">
                  max repair attempts: <span className="text-accent">{maxAttempts}</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={maxAttempts}
                  onChange={(e) => setMaxAttempts(Number(e.target.value))}
                  className="w-full accent-accent cursor-pointer mt-2"
                />
              </div>

              <div className="md:col-span-2 pt-2">
                <label className="block text-ink font-bold mb-1.5">skip post-success review agents</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'critique', label: 'critique agent' },
                    { id: 'test', label: 'unit test agent' },
                    { id: 'performance', label: 'performance agent' },
                    { id: 'security_audit', label: 'security audit agent' },
                    { id: 'docs', label: 'documentation agent' },
                  ].map((agent) => (
                    <button
                      key={agent.id}
                      type="button"
                      onClick={() => toggleSkipAgent(agent.id)}
                      className={`px-2.5 py-1 text-xs border transition-colors cursor-pointer font-mono ${
                        skipAgents.includes(agent.id)
                          ? 'border-border text-ink-tertiary line-through bg-surface-sunken'
                          : 'border-border-strong text-ink bg-surface hover:bg-canvas'
                      }`}
                    >
                      {agent.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </form>

      {/* Pipeline Stepper with Viewfinder Corner Brackets */}
      <div className="space-y-2">
        <div className="text-xs font-mono font-bold uppercase tracking-wider text-ink-secondary">
          02 // pipeline viewfinder state:
        </div>
        <PipelineStepper steps={pipelineSteps} />
      </div>

      {/* Execution Results & Attempt Stream */}
      {displayRun && (
        <div className="space-y-4 pt-2 animate-slide-in">
          <div className="bg-surface border border-border p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className={`h-9 w-9 border flex items-center justify-center ${
                isComplete
                  ? isSuccess
                    ? 'bg-status-success-subtle border-status-success/40 text-status-success'
                    : 'bg-status-danger-subtle border-status-danger/40 text-status-danger'
                  : 'bg-surface-sunken border-border text-accent'
              }`}>
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold text-ink">{displayRun.run_id}</span>
                  <StatusBadge status={displayRun.final_status} />
                </div>
                <div className="text-[11px] text-ink-secondary font-mono mt-0.5">
                  attempts: {displayRun.attempts.length} / {displayRun.total_attempts || maxAttempts}
                  {latestAttempt?.latency_ms && (
                    <span className="ml-2 text-ink-tertiary">· {latestAttempt.latency_ms}ms last</span>
                  )}
                </div>
              </div>
            </div>

            <Link
              to={`/runs/${displayRun.run_id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-surface hover:bg-surface-sunken border border-border-strong text-xs font-mono font-semibold text-accent transition-colors"
            >
              <span>inspect full ledger →</span>
            </Link>
          </div>

          {/* Render attempts */}
          <div className="space-y-3">
            {displayRun.attempts.map((attempt) => (
              <AttemptCard
                key={attempt.attempt_id ?? attempt.attempt_number}
                attempt={attempt}
                defaultExpanded={attempt.attempt_number === displayRun.attempts.length}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
