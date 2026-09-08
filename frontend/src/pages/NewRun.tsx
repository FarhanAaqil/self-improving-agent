import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  AlertCircle,
  ExternalLink,
  Layers,
  Loader2,
  Play,
  Sliders,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { generateAndRepair, getRun } from '../api/client'
import type { RunOut } from '../api/types'
import AttemptCard from '../components/AttemptCard'
import PipelineStepper, { type PipelineStep } from '../components/PipelineStepper'
import StatusBadge from '../components/StatusBadge'

const TEMPLATE_PROMPTS = [
  {
    title: 'LRU Cache',
    category: 'Algorithms',
    prompt:
      'Write a complete LRUCache class in Python with get(key) and put(key, value) in O(1) time complexity using a doubly linked list and hashmap. Include self-tests asserting eviction order and capacity limits.',
  },
  {
    title: 'Parse Access Logs',
    category: 'Regex & Parsing',
    prompt:
      'Write a function parse_access_logs(logs) that parses web server log lines with regex, extracts client IP addresses, HTTP methods, and status codes, and returns a dictionary counting status codes per unique IP. Test with sample log strings.',
  },
  {
    title: 'Validate Binary Search Tree',
    category: 'Data Structures',
    prompt:
      'Write a function is_valid_bst(root) that checks whether a binary tree is a valid Binary Search Tree with strictly increasing in-order traversal values. Include test cases with valid and invalid trees.',
  },
  {
    title: 'Safe Path Traversal Guard',
    category: 'Security',
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

  // Polling query: polls GET /runs/{run_id} while the agent is running
  const { data: polledRun } = useQuery<RunOut>({
    queryKey: ['run', activeRunId],
    queryFn: () => getRun(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const state = query.state.data
      if (!state) return 1000
      const isTerminal = ['success', 'failed', 'max_retries_exceeded'].includes(state.final_status)
      return isTerminal ? false : 1200
    },
  })

  const mutation = useMutation({
    mutationFn: generateAndRepair,
    onSuccess: (data) => {
      setActiveRunId(data.run_id)
    },
  })

  const toggleAgent = (agent: string) => {
    setSkipAgents((prev) =>
      prev.includes(agent) ? prev.filter((a) => a !== agent) : [...prev, agent]
    )
  }

  const handleSelectTemplate = (prompt: string) => {
    setTaskDescription(prompt)
    setValidationError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!taskDescription.trim()) {
      setValidationError('Task description cannot be empty.')
      return
    }
    if (taskDescription.trim().length < 5) {
      setValidationError('Task description must be at least 5 characters long.')
      return
    }
    setValidationError(null)
    setActiveRunId(null)

    mutation.mutate({
      task_description: taskDescription.trim(),
      model,
      max_attempts: maxAttempts,
      skip_agents: skipAgents,
    })
  }

  const runData = polledRun || mutation.data
  const isExecuting = mutation.isPending || (runData && runData.final_status === 'running')

  // Compute live pipeline steps
  const getPipelineSteps = (): PipelineStep[] => {
    const isRunning = isExecuting
    const isComplete = runData && ['success', 'failed', 'max_retries_exceeded'].includes(runData.final_status)
    const isSuccess = runData?.final_status === 'success'

    const lastAttempt = runData?.attempts?.[runData.attempts.length - 1]

    return [
      {
        id: 'generate',
        name: 'Generate',
        label: 'Synthesis',
        state: isRunning
          ? 'active'
          : runData
          ? 'passed'
          : 'pending',
      },
      {
        id: 'critique',
        name: 'Critique',
        label: 'Confidence review',
        state: skipAgents.includes('critique')
          ? 'skipped'
          : isRunning
          ? 'pending'
          : lastAttempt?.critique_confidence !== null && lastAttempt?.critique_confidence !== undefined
          ? 'passed'
          : isComplete && isSuccess
          ? 'passed'
          : 'pending',
      },
      {
        id: 'test',
        name: 'Test',
        label: 'Unit test suite',
        state: skipAgents.includes('test')
          ? 'skipped'
          : lastAttempt?.generated_tests
          ? 'passed'
          : isComplete && !isSuccess
          ? 'failed'
          : 'pending',
      },
      {
        id: 'performance',
        name: 'Performance',
        label: 'Complexity analysis',
        state: skipAgents.includes('performance')
          ? 'skipped'
          : lastAttempt?.performance_notes
          ? 'passed'
          : 'pending',
      },
      {
        id: 'security',
        name: 'Security Audit',
        label: 'AST AST analysis',
        state: skipAgents.includes('security_audit')
          ? 'skipped'
          : lastAttempt?.security_audit
          ? 'passed'
          : 'pending',
      },
      {
        id: 'docs',
        name: 'Document',
        label: 'Docstrings & typing',
        state: skipAgents.includes('docs')
          ? 'skipped'
          : isComplete && isSuccess
          ? 'passed'
          : 'pending',
      },
    ]
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">New Run</h1>
        <p className="text-sm text-ink-secondary mt-1">
          Generate code in a locked-down container sandbox with autonomous error critique and multi-agent verification.
        </p>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-surface border border-border rounded p-5 space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="task" className="text-sm font-medium text-ink">
                Task description <span className="text-status-danger">*</span>
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
              className="w-full bg-surface-sunken border border-border rounded p-3 text-sm text-ink placeholder-ink-tertiary focus:outline-none focus:border-accent focus:bg-surface transition-all font-mono"
            />
            {validationError && (
              <div className="flex items-center gap-1.5 text-xs text-status-danger mt-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{validationError}</span>
              </div>
            )}
          </div>

          {/* Template Quick-Picks as plain text chips */}
          <div>
            <div className="text-xs font-medium text-ink-secondary mb-1.5">Template quick-picks:</div>
            <div className="flex flex-wrap gap-2">
              {TEMPLATE_PROMPTS.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => handleSelectTemplate(item.prompt)}
                  className="px-2.5 py-1 text-xs text-ink-secondary hover:text-ink bg-surface-sunken hover:bg-canvas border border-border rounded transition-colors cursor-pointer"
                >
                  <span className="font-mono text-[11px] text-accent mr-1.5 font-semibold">[{item.category}]</span>
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
              className="flex items-center gap-1.5 text-xs text-ink-secondary hover:text-ink transition-colors cursor-pointer"
            >
              <Sliders className="h-3.5 w-3.5" />
              <span>{showAdvanced ? 'Hide runtime settings' : 'Runtime settings'}</span>
            </button>

            <button
              type="submit"
              disabled={taskDescription.trim().length < 5 || isExecuting}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors cursor-pointer"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Agent running...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  <span>Execute task</span>
                </>
              )}
            </button>
          </div>

          {/* Runtime Settings Accordion */}
          {showAdvanced && (
            <div className="pt-4 border-t border-border grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-ink font-medium mb-1">Inference model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-surface border border-border rounded p-2 text-ink font-mono focus:outline-none focus:border-accent"
                >
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (primary)</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (fast)</option>
                </select>
              </div>

              <div>
                <label className="block text-ink font-medium mb-1">
                  Max repair attempts: <span className="font-mono text-accent">{maxAttempts}</span>
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
                <label className="block text-ink font-medium mb-1.5">Skip review agents</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'critique', label: 'Critique Agent' },
                    { id: 'test', label: 'Unit Test Agent' },
                    { id: 'performance', label: 'Performance Agent' },
                    { id: 'security_audit', label: 'Security Audit Agent' },
                    { id: 'docs', label: 'Documentation Agent' },
                  ].map((agent) => (
                    <button
                      key={agent.id}
                      type="button"
                      onClick={() => toggleAgent(agent.id)}
                      className={`px-2.5 py-1 rounded border text-xs font-mono transition-colors cursor-pointer ${
                        skipAgents.includes(agent.id)
                          ? 'bg-status-danger-subtle border-status-danger/30 text-status-danger'
                          : 'bg-surface border-border text-ink-secondary hover:border-border-strong'
                      }`}
                    >
                      {skipAgents.includes(agent.id) ? `✕ Skip ${agent.label}` : `✓ Run ${agent.label}`}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </form>

      {/* Live Pipeline Stepper */}
      {(isExecuting || runData) && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-ink-secondary">Verification pipeline:</div>
          <PipelineStepper steps={getPipelineSteps()} />
        </div>
      )}

      {/* Mutation Error Notification */}
      {mutation.isError && (
        <div className="p-4 rounded bg-status-danger-subtle border border-status-danger/30 text-status-danger text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold">Execution failed</div>
            <div className="text-xs text-status-danger/90 font-mono">
              {mutation.error instanceof Error ? mutation.error.message : 'Unknown error occurred'}
            </div>
          </div>
        </div>
      )}

      {/* Active Run Live Results */}
      {runData && (
        <div className="space-y-4 pt-2">
          {/* Run Status Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded bg-surface border border-border gap-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded bg-surface-sunken border border-border flex items-center justify-center text-accent">
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-ink">
                    {runData.run_id}
                  </span>
                  <StatusBadge status={runData.final_status} />
                </div>
                <div className="text-xs text-ink-secondary mt-0.5">
                  {runData.attempts.length} of {maxAttempts} attempt{maxAttempts > 1 ? 's' : ''} executed
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Link
                to={`/runs/${runData.run_id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface hover:bg-canvas border border-border text-xs font-medium text-ink transition-colors"
              >
                <span>Full run detail</span>
                <ExternalLink className="h-3.5 w-3.5 text-ink-secondary" />
              </Link>
            </div>
          </div>

          {/* Attempt by attempt cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-medium text-ink-secondary px-1">
              <span>Attempt execution sequence</span>
              {isExecuting && (
                <span className="inline-flex items-center gap-1.5 text-accent font-mono">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Verifying in sandbox...
                </span>
              )}
            </div>

            {runData.attempts.map((attempt) => (
              <AttemptCard
                key={attempt.attempt_id ?? attempt.attempt_number}
                attempt={attempt}
                defaultExpanded={attempt.attempt_number === runData.attempts.length}
              />
            ))}

            {isExecuting && runData.attempts.length === 0 && (
              <div className="p-8 rounded border border-border bg-surface flex flex-col items-center justify-center text-center space-y-3">
                <Loader2 className="h-6 w-6 text-accent animate-spin" />
                <div className="text-sm font-medium text-ink">
                  Synthesizing initial code solution...
                </div>
                <div className="text-xs text-ink-secondary max-w-sm">
                  The LLM is generating source code, which will immediately be mounted read-only into an isolated Docker container for verification.
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
