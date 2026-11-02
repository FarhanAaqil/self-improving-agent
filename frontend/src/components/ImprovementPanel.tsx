import { useQuery } from '@tanstack/react-query'
import { TrendingUp } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getImprovement } from '../api/client'
import type { MemoryBucket } from '../api/types'
import { Panel, Skeleton } from './ui'

const rate = (b: MemoryBucket) => (b.runs ? b.first_try / b.runs : null)

/** "Is it getting better?" Daily first-try and solve rates, plus runs with vs. without memory. */
export default function ImprovementPanel() {
  const { data, isLoading } = useQuery({ queryKey: ['improvement'], queryFn: () => getImprovement(60) })

  if (isLoading) return <Skeleton className="h-72" />
  if (!data) return null

  const points = data.daily.map((d) => ({
    day: d.day.slice(5),
    firstTry: d.first_try_rate === null ? null : Math.round(d.first_try_rate * 100),
    solved: d.solve_rate === null ? null : Math.round(d.solve_rate * 100),
    runs: d.runs,
  }))
  const withMem = data.memory_effect.with_memory
  const without = data.memory_effect.without_memory
  const withRate = rate(withMem)
  const withoutRate = rate(without)
  const enough = withMem.runs >= 3 && without.runs >= 3

  return (
    <Panel title="is it getting better?" icon={<TrendingUp className="h-3.5 w-3.5 text-cyan" aria-hidden />}>
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div>
          {points.length >= 2 ? (
            <>
              <div className="h-56" role="img" aria-label="Daily first-try and solve rates">
                <ResponsiveContainer>
                  <LineChart data={points} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid stroke="rgb(var(--chart-grid))" vertical={false} />
                    <XAxis dataKey="day" tick={{ fill: 'rgb(var(--ink-muted))', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} unit="%" tick={{ fill: 'rgb(var(--ink-muted))', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: 'rgb(var(--surface))', border: '1px solid rgb(var(--border))', borderRadius: 0, fontSize: 12 }}
                      formatter={(v, name) => [`${v}%`, name]}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="solved" name="solved" stroke="rgb(var(--chart-1))" strokeWidth={2} connectNulls dot={{ r: 4, strokeWidth: 2, stroke: 'rgb(var(--surface))' }} />
                    <Line type="monotone" dataKey="firstTry" name="solved on first try" stroke="rgb(var(--chart-2))" strokeWidth={2} connectNulls dot={{ r: 4, strokeWidth: 2, stroke: 'rgb(var(--surface))' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <table className="sr-only">
                <caption>Daily rates</caption>
                <thead><tr><th>day</th><th>runs</th><th>solved</th><th>first try</th></tr></thead>
                <tbody>{points.map((p) => <tr key={p.day}><td>{p.day}</td><td>{p.runs}</td><td>{p.solved}%</td><td>{p.firstTry}%</td></tr>)}</tbody>
              </table>
            </>
          ) : (
            <p className="text-sm text-ink-muted">The trend appears after runs on at least two different days.</p>
          )}
        </div>
        <div className="space-y-3">
          <div className="eyebrow">first-try success</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-cyan/40 bg-cyan-subtle p-3">
              <div className="font-mono text-[11px] text-cyan">with recalled memory</div>
              <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-ink">{withRate === null ? '—' : `${Math.round(withRate * 100)}%`}</div>
              <div className="font-mono text-[10px] text-ink-muted">{withMem.runs} runs</div>
            </div>
            <div className="border border-border bg-surface-sunken p-3">
              <div className="font-mono text-[11px] text-ink-secondary">fresh start</div>
              <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-ink">{withoutRate === null ? '—' : `${Math.round(withoutRate * 100)}%`}</div>
              <div className="font-mono text-[10px] text-ink-muted">{without.runs} runs</div>
            </div>
          </div>
          <p className="text-xs text-ink-secondary">
            {enough
              ? 'Runs that recalled a memory compared with runs that started fresh. Tasks differ, so read this as a signal, not proof.'
              : 'Needs at least three runs in each group before the comparison means anything.'}
          </p>
        </div>
      </div>
    </Panel>
  )
}
