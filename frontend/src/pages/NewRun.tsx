import { useState } from 'react'
import { AlertCircle, ArrowRight, Play, Sliders } from 'lucide-react'

export default function NewRun() {
  const [taskDescription, setTaskDescription] = useState('')
  const [model, setModel] = useState('llama-3.3-70b-versatile')
  const [maxAttempts, setMaxAttempts] = useState(3)
  const [skipAgents, setSkipAgents] = useState<string[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

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
    // Submitting will be wired in commit 64
  }

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
              disabled={taskDescription.trim().length < 5}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg shadow-sm shadow-indigo-500/20 transition-all cursor-pointer"
            >
              <Play className="h-4 w-4 fill-white" />
              <span>Execute Task</span>
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
    </div>
  )
}
