import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  AlertCircle,
  ExternalLink,
  Layers,
  Lightbulb,
  Loader2,
  Play,
  Sliders,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { generateAndRepair, getRun } from '../api/client'
import type { RunOut } from '../api/types'
import AttemptCard from '../components/AttemptCard'
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">New Task Run</h1>
        <p className="text-sm text-slate-400 mt-1">
          Submit a programming task to the agent. Code is generated, executed in the isolated Docker sandbox, and autonomously repaired on error.
        </p>
      </div>

      {/* Template Prompts */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
          <Lightbulb className="h-3.5 w-3.5 text-amber-400" />
          <span>Quick Template Prompts</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {TEMPLATE_PROMPTS.map((item) => (
            <button
              key={item.title}
              type="button"
              onClick={() => handleSelectTemplate(item.prompt)}
              className="text-left p-3 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all group flex flex-col justify-between cursor-pointer"
            >
              <div>
                <span className="text-[10px] uppercase font-mono text-indigo-400 font-semibold block mb-0.5">
                  {item.category}
                </span>
                <span className="text-xs font-medium text-slate-200 group-hover:text-white transition-colors block">
                  {item.title}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 line-clamp-2 mt-1.5 font-mono">
                {item.prompt}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="task" className="text-sm font-medium text-slate-200">
                Task Description <span className="text-rose-400">*</span>
              </label>
              <span className="text-xs text-slate-500 font-mono">
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
              placeholder="e.g. Write a function parse_log_dates(lines) that extracts ISO-8601 timestamps using regex and returns a sorted list of datetime objects."
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all font-mono"
            />
            {validationError && (
              <div className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{validationError}</span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              <Sliders className="h-3.5 w-3.5" />
              <span>{showAdvanced ? 'Hide runtime settings' : 'Runtime settings'}</span>
            </button>

            <button
              type="submit"
              disabled={taskDescription.trim().length < 5 || isExecuting}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg shadow-sm shadow-indigo-500/20 transition-all cursor-pointer"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Agent Working...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  <span>Execute Task</span>
                </>
              )}
            </button>
          </div>

          {showAdvanced && (
            <div className="pt-4 border-t border-slate-800/60 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Inference Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-md p-2 text-slate-200 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (primary)</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (fast)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Max Repair Attempts: <span className="font-mono text-indigo-400">{maxAttempts}</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={maxAttempts}
                  onChange={(e) => setMaxAttempts(Number(e.target.value))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
              </div>

              <div className="md:col-span-2 pt-2">
                <label className="block text-slate-300 font-medium mb-1.5">Skip Review Agents</label>
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
                      className={`px-2.5 py-1 rounded-md border text-xs font-mono transition-colors ${
                        skipAgents.includes(agent.id)
                          ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
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

      {/* Mutation Error Notification */}
      {mutation.isError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-rose-400" />
          <div className="space-y-1">
            <div className="font-semibold">Execution Failed</div>
            <div className="text-xs text-rose-300/90 font-mono">
              {mutation.error instanceof Error ? mutation.error.message : 'Unknown error occurred'}
            </div>
          </div>
        </div>
      )}

      {/* Active Run Live Results (Without Page Reload) */}
      {runData && (
        <div className="space-y-4 pt-2">
          {/* Run Status Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl bg-slate-900/80 border border-slate-800 gap-3">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-mono text-sm font-semibold">
                <Layers className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-slate-100">
                    {runData.run_id}
                  </span>
                  <StatusBadge status={runData.final_status} />
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {runData.attempts.length} of {maxAttempts} attempt{maxAttempts > 1 ? 's' : ''} executed
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Link
                to={`/runs/${runData.run_id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 transition-colors"
              >
                <span>Full Run Detail</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>

          {/* Attempt by attempt cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-medium text-slate-400 px-1">
              <span>Attempt Execution Timeline</span>
              {isExecuting && (
                <span className="inline-flex items-center gap-1.5 text-indigo-400 font-mono">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Generating & verifying in sandbox...
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
              <div className="p-8 rounded-xl border border-slate-800/80 bg-slate-900/30 flex flex-col items-center justify-center text-center space-y-3">
                <Loader2 className="h-6 w-6 text-indigo-500 animate-spin" />
                <div className="text-sm font-medium text-slate-300">
                  Synthesizing initial code solution...
                </div>
                <div className="text-xs text-slate-500 max-w-sm">
                  The LLM is constructing Python source code, which will immediately be mounted read-only into an isolated Docker container for verification.
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
