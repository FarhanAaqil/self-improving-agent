import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, Brain, FlaskConical, Play, ShieldCheck, Sliders, Swords, Wrench } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { listRuns, searchMemory, startComparison, startRun } from '../api/client'
import { ErrorNote, Kbd, PageHeader, StatusPill } from '../components/ui'
import { useHealth } from '../hooks/useHealth'
import { usePreferences } from '../hooks/usePreferences'
import { relativeTime } from '../lib/format'

const TEMPLATES = [
  {
    tag: 'algorithms',
    title: 'LRU cache',
    prompt:
      'Write a class LRUCache(capacity) with get(key) and put(key, value), both O(1). get returns -1 for missing keys; put evicts the least recently used key when over capacity.',
  },
  {
    tag: 'parsing',
    title: 'Access log stats',
    prompt:
      'Write parse_access_logs(lines) that parses Apache common-log lines and returns a dict mapping each client IP to a dict of status-code counts. Skip malformed lines instead of crashing.',
  },
  {
    tag: 'intervals',
    title: 'Merge intervals',
    prompt:
      'Write merge_intervals(intervals) that merges overlapping [start, end] pairs and returns them sorted. Touching intervals like [1,2] and [2,3] merge. An empty list returns [].',
  },
  {
    tag: 'security',
    title: 'Safe path join',
    prompt:
      "Write safe_join(base_dir, user_path) that resolves an untrusted relative path inside base_dir and raises ValueError if the result would escape base_dir (for example '../etc/passwd' or an absolute path).",
  },
]

const AGENTS = [
  { id: 'test', label: 'spec tests', hint: 'write tests before code' },
  { id: 'mutation', label: 'test strength', hint: 'break the code on purpose, then write stricter tests' },
  { id: 'critique', label: 'diagnosis', hint: 'explain failures' },
  { id: 'performance', label: 'performance', hint: 'big-O review' },
  { id: 'security_audit', label: 'security audit', hint: 'LLM review + bandit' },
  { id: 'docs', label: 'docstrings', hint: 'kept only if still passing' },
]

const FLOW = [
  { icon: Brain, label: 'recall', tone: 'text-cyan' },
  { icon: FlaskConical, label: 'spec tests', tone: 'text-accent-ink' },
  { icon: Play, label: 'generate', tone: 'text-accent-ink' },
  { icon: ShieldCheck, label: 'sandbox', tone: 'text-ink' },
  { icon: Wrench, label: 'repair', tone: 'text-status-danger' },
]

function useDebounced<T>(value: T, ms: number) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

export default function Workbench() {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: health } = useHealth()
  const { prefs } = usePreferences()
  const forkedTask = (location.state as { task?: string } | null)?.task

  const [task, setTask] = useState(forkedTask ?? '')
  const [model, setModel] = useState(prefs.defaultModel)
  const [attempts, setAttempts] = useState(prefs.defaultAttempts)
  const [skip, setSkip] = useState<string[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [race, setRace] = useState<string[]>([])

  const query = useDebounced(task.trim(), 600)
  const { data: recall } = useQuery({
    queryKey: ['memory-preview', query],
    queryFn: () => searchMemory(query, 0.6),
    enabled: Boolean(health?.memory_enabled) && query.length >= 20,
    staleTime: 60_000,
    retry: false,
  })
  const recalled = recall?.items ?? []

  const { data: recent } = useQuery({ queryKey: ['runs-recent'], queryFn: () => listRuns({ pageSize: 5 }) })

  const racing = race.length >= 2
  const run = useMutation({
    mutationFn: async () => {
      const base = { task_description: task.trim(), max_attempts: attempts, skip_agents: skip }
      if (racing) {
        const res = await startComparison({ ...base, models: race })
        return `/compare/${res.group_id}`
      }
      const res = await startRun({ ...base, model: model || health?.default_model || null })
      return `/runs/${res.run_id}`
    },
    onSuccess: (to) => navigate(to),
  })

  const ready = task.trim().length >= 5 && !run.isPending
  const submit = () => ready && run.mutate()

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="workbench"
        title="What should I build?"
        lede="Describe a Python task. I write spec tests first, then code that has to pass them inside a locked container, and I fix my own mistakes until it does."
      />

      <section className="panel shadow-ledger">
        <label htmlFor="task" className="sr-only">Task description</label>
        <textarea
          id="task"
          rows={5}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              submit()
            }
          }}
          maxLength={4000}
          placeholder="e.g. Write a function top_k_words(text, k) that returns the k most frequent words, ties broken alphabetically…"
          className="ruled block w-full resize-y bg-surface px-5 py-4 font-mono text-sm leading-7 text-ink placeholder:text-ink-tertiary focus:outline-none"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3">
          <div className="flex items-center gap-3 font-mono text-[11px] text-ink-muted">
            <button type="button" onClick={() => setShowSettings((s) => !s)} className="btn-ghost px-2 py-1" aria-expanded={showSettings}>
              <Sliders className="h-3.5 w-3.5" aria-hidden />
              settings
            </button>
            <span>{racing ? `${race.length} models racing` : model || health?.default_model || 'default model'} · {attempts} attempts</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[11px] text-ink-muted sm:inline">
              <Kbd>Ctrl</Kbd> + <Kbd>Enter</Kbd>
            </span>
            <button type="button" onClick={submit} disabled={!ready || health?.docker_available === false} className="btn-primary">
              <Play className="h-3.5 w-3.5 fill-current" aria-hidden />
              {run.isPending ? 'starting…' : racing ? `race ${race.length} models` : 'run it'}
            </button>
          </div>
        </div>

        {showSettings && (
          <div className="grid gap-5 border-t border-border bg-surface-raised px-4 py-4 md:grid-cols-2">
            <label className="block">
              <span className="eyebrow">model</span>
              <select value={model || health?.default_model || ''} onChange={(e) => setModel(e.target.value)} className="input mt-1 font-mono">
                {(health?.models ?? []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                    {m === health?.default_model ? ' (default)' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="eyebrow">max attempts: <span className="text-accent-ink">{attempts}</span></span>
              <input type="range" min={1} max={10} value={attempts} onChange={(e) => setAttempts(Number(e.target.value))} className="mt-3 w-full accent-[rgb(var(--accent))]" />
            </label>
            {(health?.models?.length ?? 0) >= 2 && (
              <fieldset className="md:col-span-2">
                <legend className="eyebrow flex items-center gap-1.5"><Swords className="h-3 w-3" aria-hidden /> race models (pick 2 to 4)</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(health?.models ?? []).map((m) => {
                    const on = race.includes(m)
                    return (
                      <button
                        key={m}
                        type="button"
                        aria-pressed={on}
                        disabled={!on && race.length >= 4}
                        onClick={() => setRace((r) => (on ? r.filter((x) => x !== m) : [...r, m]))}
                        className={`chip px-2.5 py-1 disabled:opacity-40 ${on ? 'border-accent bg-accent-subtle text-accent-ink' : 'border-border bg-surface text-ink-secondary'}`}
                      >
                        {m}
                      </button>
                    )
                  })}
                </div>
              </fieldset>
            )}
            <fieldset className="md:col-span-2">
              <legend className="eyebrow">agents</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {AGENTS.map((a) => {
                  const on = !skip.includes(a.id)
                  return (
                    <button
                      key={a.id}
                      type="button"
                      aria-pressed={on}
                      title={a.hint}
                      onClick={() => setSkip((s) => (on ? [...s, a.id] : s.filter((x) => x !== a.id)))}
                      className={`chip px-2.5 py-1 ${on ? 'border-border-strong bg-surface text-ink' : 'border-border bg-surface-sunken text-ink-muted line-through'}`}
                    >
                      {a.label}
                    </button>
                  )
                })}
              </div>
            </fieldset>
          </div>
        )}
      </section>

      {health && !health.docker_available && (
        <ErrorNote error={new Error('The sandbox is offline on this server, so I can’t run code right now. Start Docker on the host to enable runs.')} />
      )}
      {run.isError && <ErrorNote error={run.error} />}

      {recalled.length > 0 && (
        <aside className="animate-rise-in border border-cyan/40 bg-cyan-subtle p-4" aria-live="polite">
          <div className="flex items-center gap-2 font-mono text-xs font-bold text-cyan">
            <Brain className="h-4 w-4" aria-hidden />
            I remember {recalled.length} similar task{recalled.length > 1 ? 's' : ''}
          </div>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-secondary">
            {recalled.slice(0, 3).map((m) => (
              <li key={m.id} className="flex gap-2">
                <span className="font-mono text-xs text-cyan">{Math.round((m.similarity ?? 0) * 100)}%</span>
                <span className="line-clamp-1">
                  {m.kind === 'fix' && m.lesson ? `Lesson: ${m.lesson}` : `Failed before: ${m.error?.split('\n').slice(-1)[0] ?? m.task}`}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      )}

      <section aria-labelledby="flow-title">
        <h2 id="flow-title" className="eyebrow mb-3">what happens when you press run</h2>
        <ol className="flex flex-wrap items-center gap-2">
          {FLOW.map(({ icon: Icon, label, tone }, i) => (
            <li key={label} className="flex items-center gap-2">
              <span className={`chip border-border bg-surface px-2.5 py-1 ${tone}`}>
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {label}
              </span>
              {i < FLOW.length - 1 && <ArrowRight className="h-3 w-3 text-ink-tertiary" aria-hidden />}
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="templates-title">
        <h2 id="templates-title" className="eyebrow mb-3">or start from one of these</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {TEMPLATES.map((t) => (
            <button
              key={t.title}
              type="button"
              onClick={() => setTask(t.prompt)}
              className="panel group p-4 text-left transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-ledger-accent"
            >
              <div className="font-mono text-[10px] uppercase tracking-wider text-accent-ink">{t.tag}</div>
              <div className="mt-1 font-mono text-sm font-bold text-ink">{t.title}</div>
              <p className="mt-1 line-clamp-2 text-xs text-ink-secondary">{t.prompt}</p>
            </button>
          ))}
        </div>
      </section>

      {recent && recent.items.length > 0 && (
        <section aria-labelledby="recent-title">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="recent-title" className="eyebrow">recent runs</h2>
            <Link to="/history" className="font-mono text-xs text-accent-ink hover:underline">all runs →</Link>
          </div>
          <ul className="panel divide-y divide-border">
            {recent.items.map((r) => (
              <li key={r.run_id}>
                <Link to={`/runs/${r.run_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-sunken">
                  <StatusPill status={r.final_status} />
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">{r.task_description}</span>
                  <span className="hidden font-mono text-[11px] text-ink-muted sm:inline">{relativeTime(r.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
