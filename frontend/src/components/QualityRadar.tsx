import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { QualityReport } from '../api/types'

const LABELS: Record<string, string> = {
  tests: 'tests',
  mutation: 'test strength',
  coverage: 'coverage',
  security: 'security',
  complexity: 'simplicity',
  performance: 'performance',
}

/** Single-series radar: the title names it, so no legend; N/A axes are listed below instead of drawn as 0. */
export default function QualityRadar({ report }: { report: QualityReport }) {
  const entries = Object.entries(report.components)
  const measured = entries.filter(([, v]) => v !== null).map(([k, v]) => ({ axis: LABELS[k] ?? k, value: Math.round((v as number) * 100) }))
  const missing = entries.filter(([, v]) => v === null).map(([k]) => LABELS[k] ?? k)

  return (
    <figure>
      {measured.length >= 3 ? (
        <div className="h-56" aria-hidden>
          <ResponsiveContainer>
            <RadarChart data={measured} outerRadius="72%">
              <PolarGrid stroke="rgb(var(--chart-grid))" />
              <PolarAngleAxis dataKey="axis" tick={{ fill: 'rgb(var(--ink-secondary))', fontSize: 11, fontFamily: 'JetBrains Mono' }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar dataKey="value" stroke="rgb(var(--chart-1))" strokeWidth={2} fill="rgb(var(--chart-1))" fillOpacity={0.12} dot={{ r: 4, strokeWidth: 2, stroke: 'rgb(var(--surface))', fill: 'rgb(var(--chart-1))' }} />
              <Tooltip
                cursor={false}
                contentStyle={{ background: 'rgb(var(--surface))', border: '1px solid rgb(var(--border))', borderRadius: 0, fontFamily: 'JetBrains Mono', fontSize: 12 }}
                formatter={(v) => [`${v} / 100`, 'score']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      ) : null}
      {/* Table view of the same numbers, always available to screen readers and print */}
      <table className="mt-2 w-full font-mono text-xs">
        <caption className="sr-only">Quality components</caption>
        <tbody>
          {measured.map((m) => (
            <tr key={m.axis} className="border-t border-border">
              <th scope="row" className="py-1 text-left font-normal text-ink-secondary">{m.axis}</th>
              <td className="py-1 text-right tabular-nums text-ink">{m.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {missing.length > 0 && (
        <figcaption className="mt-2 text-[11px] text-ink-muted">Not measured: {missing.join(', ')}</figcaption>
      )}
    </figure>
  )
}
