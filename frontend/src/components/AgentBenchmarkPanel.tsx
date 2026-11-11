import { useQuery } from '@tanstack/react-query'
import { Scale } from 'lucide-react'
import { useState } from 'react'
import { getAgentBenchmarks } from '../api/client'
import type { AgentBenchCondition } from '../api/types'
import { Chip, Panel, Skeleton } from './ui'

const LABELS: Record<string, string> = {
  baseline: 'Single shot',
  agent: 'Agent',
  hardened: 'Agent + stricter tests',
  cold: 'Agent + stricter tests',
  warm: 'Same tasks again, with memory',
}

function Rate({ value, ci }: { value?: number; ci?: [number, number] }) {
  if (value === undefined) return <span className="text-ink-muted">—</span>
  return (
    <span>
      <span className="font-bold text-ink">{value.toFixed(1)}%</span>
      {ci && <span className="ml-1 text-[10px] text-ink-muted">{ci[0]}–{ci[1]}</span>}
    </span>
  )
}

function finding(conditions: AgentBenchCondition[]): string[] {
  const by = Object.fromEntries(conditions.map((c) => [c.condition, c]))
  const lines: string[] = []
  const plain = by.agent
  const strict = by.cold ?? by.hardened
  if (by.baseline && (strict ?? plain)) {
    const best = strict ?? plain
    const gain = best.hidden_pass_rate - by.baseline.hidden_pass_rate
    lines.push(
      `Against hidden tests the agent's code is correct ${best.hidden_pass_rate.toFixed(1)}% of the time, versus ${by.baseline.hidden_pass_rate.toFixed(1)}% for a single shot (${gain >= 0 ? '+' : ''}${gain.toFixed(1)} points).`,
    )
  }
  if (plain?.false_verified_rate !== undefined) {
    lines.push(
      `When the agent stamps a run "verified", it is actually wrong ${plain.false_verified_rate.toFixed(1)}% of the time` +
        (strict?.false_verified_rate !== undefined ? `, and ${strict.false_verified_rate.toFixed(1)}% once it writes stricter tests.` : '.'),
    )
  }
  if (by.cold && by.warm) {
    const d = by.warm.hidden_pass_rate - by.cold.hidden_pass_rate
    lines.push(
      `Meeting the same tasks a second time with memory changed correctness by ${d >= 0 ? '+' : ''}${d.toFixed(1)} points ` +
        `(${by.warm.runs_that_recalled_memory ?? 0} of ${by.warm.problems} runs recalled something).`,
    )
  }
  return lines
}

/** The real pipeline, judged by hidden HumanEval+ inputs it never sees. */
export default function AgentBenchmarkPanel() {
  const { data, isLoading } = useQuery({ queryKey: ['agent-benchmarks'], queryFn: getAgentBenchmarks })
  const [selected, setSelected] = useState(0)

  if (isLoading) return <Skeleton className="h-64" />
  const items = data?.items ?? []
  if (!items.length) {
    return (
      <Panel title="does verified mean correct?" icon={<Scale className="h-3.5 w-3.5 text-cyan" aria-hidden />}>
        <p className="text-sm text-ink-secondary">
          No run yet. <code className="font-mono">python -m eval.agent_benchmark</code> runs the real pipeline and judges
          its code with hidden HumanEval+ inputs.
        </p>
      </Panel>
    )
  }
  const run = items[Math.min(selected, items.length - 1)]
  const grid = run.grid[run.conditions[run.conditions.length - 1]?.condition] ?? []

  return (
    <Panel
      title="does verified mean correct?"
      icon={<Scale className="h-3.5 w-3.5 text-cyan" aria-hidden />}
      actions={
        items.length > 1 ? (
          <div className="flex gap-1" role="tablist" aria-label="Model">
            {items.map((item, i) => (
              <button
                key={item.eval_id}
                type="button"
                role="tab"
                aria-selected={i === selected}
                onClick={() => setSelected(i)}
                className={`chip px-2 py-0.5 ${i === selected ? 'border-ink bg-ink text-ink-inverse' : 'border-border bg-surface text-ink-secondary'}`}
              >
                {item.model}
              </button>
            ))}
          </div>
        ) : (
          <Chip tone="muted">{run.model}</Chip>
        )
      }
    >
      <p className="mb-3 font-mono text-[11px] text-ink-muted">
        {run.total_problems} HumanEval+ problems (about 750 hidden inputs each) · {run.date} · the agent never sees the
        hidden inputs or the verdict
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left font-mono text-xs">
          <caption className="sr-only">Agent benchmark by condition</caption>
          <thead className="border-b border-border text-[10px] uppercase tracking-wider text-ink-muted">
            <tr>
              <th scope="col" className="py-2 pr-3 font-medium">setup</th>
              <th scope="col" className="py-2 pr-3 font-medium">actually correct</th>
              <th scope="col" className="py-2 pr-3 font-medium">stamped verified</th>
              <th scope="col" className="py-2 pr-3 font-medium">verified but wrong</th>
              <th scope="col" className="py-2 pr-3 font-medium">first try</th>
              <th scope="col" className="py-2 pr-3 font-medium">attempts</th>
              <th scope="col" className="py-2 font-medium">tokens</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {run.conditions.map((c) => (
              <tr key={c.condition}>
                <th scope="row" className="py-2 pr-3 font-normal text-ink">
                  {LABELS[c.condition] ?? c.condition}
                  <div className="font-sans text-[10px] text-ink-muted">{c.description}</div>
                </th>
                <td className="py-2 pr-3"><Rate value={c.hidden_pass_rate} ci={c.hidden_pass_ci95} /></td>
                <td className="py-2 pr-3"><Rate value={c.self_verified_rate} /></td>
                <td className="py-2 pr-3">
                  {c.false_verified_rate === undefined ? <span className="text-ink-muted">—</span> : (
                    <span className={c.false_verified ? 'text-status-danger' : 'text-status-success'}>
                      <span className="font-bold">{c.false_verified_rate.toFixed(1)}%</span>
                      <span className="ml-1 text-[10px] text-ink-muted">{c.false_verified} of {c.self_verified}</span>
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3"><Rate value={c.first_try_rate} /></td>
                <td className="py-2 pr-3 text-ink">{c.avg_attempts ?? '—'}</td>
                <td className="py-2 text-ink-secondary">{c.avg_tokens ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="mt-4 space-y-1.5 border-t border-border pt-3 text-sm text-ink-secondary">
        {finding(run.conditions).map((line) => <li key={line}>{line}</li>)}
      </ul>

      {grid.length > 0 && (
        <>
          <ul className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(22px,1fr))] gap-[2px]" aria-label="Per-problem outcome in the final setup">
            {grid.map((cell) => {
              const tone = cell.correct ? 'bg-status-success' : cell.verified ? 'bg-status-danger' : 'bg-surface-sunken'
              const label = `${cell.id}: ${cell.correct ? 'correct' : cell.verified ? 'stamped verified but wrong' : 'not solved, and not stamped'}`
              return <li key={cell.id} title={label} aria-label={label} className={`aspect-square ${tone}`} />
            })}
          </ul>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-ink-secondary">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 bg-status-success" aria-hidden />correct</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 bg-status-danger" aria-hidden />stamped verified, but wrong</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 border border-border bg-surface-sunken" aria-hidden />unsolved, honestly not stamped</span>
          </div>
        </>
      )}
    </Panel>
  )
}
