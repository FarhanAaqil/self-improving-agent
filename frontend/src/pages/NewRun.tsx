import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { AlertCircle, Loader2, Play, Sliders } from 'lucide-react'
import { generateAndRepair, getRun } from '../api/client'
import type { RunOut } from '../api/types'

export default function NewRun() {
  const [taskDescription, setTaskDescription] = useState('')
  const [model, setModel] = useState('llama-3.3-70b-versatile')
  const [maxAttempts, setMaxAttempts] = useState(3)
  const [skipAgents, setSkipAgents] = useState<string[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)

  // Polling hook: polls GET /runs/{run_id} while the run is running or pending
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

  const currentRun = polledRun || mutation.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">New Task Run</h1>
        <p className="text-sm text-slate-400 mt-1">
          Submit a programming task to the agent. Code is generated, executed in the isolated Docker sandbox, and autonomously repaired on error.
        </p>
      </div>

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
              disabled={taskDescription.trim().length < 5 || mutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg shadow-sm shadow-indigo-500/20 transition-all cursor-pointer"
            >
              {mutation.isPending ? (
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

      {currentRun && (
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 font-mono">
          Run {currentRun.run_id} status: {currentRun.final_status} ({currentRun.attempts.length} attempts)
        </div>
      )}
    </div>
  )
}
