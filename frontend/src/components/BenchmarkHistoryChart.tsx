import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface HistoryPoint {
  date: string
  baseline: number
  agent: number
}

/** Baseline vs agent across benchmark runs (loaded lazily with the charts library). */
export default function BenchmarkHistoryChart({ points }: { points: HistoryPoint[] }) {
  return (
    <>
    <div className="h-64" role="img" aria-label="Baseline and agent solve rate across benchmark runs">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid stroke="rgb(var(--chart-grid))" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: 'rgb(var(--ink-muted))', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} unit="%" tick={{ fill: 'rgb(var(--ink-muted))', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: 'rgb(var(--surface))', border: '1px solid rgb(var(--border))', borderRadius: 0, fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="agent" name="agent solve@k" stroke="rgb(var(--chart-1))" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: 'rgb(var(--surface))' }} />
          <Line type="monotone" dataKey="baseline" name="baseline" stroke="rgb(var(--chart-2))" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: 'rgb(var(--surface))' }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    <table className="sr-only">
      <caption>Benchmark history</caption>
      <thead><tr><th>date</th><th>baseline</th><th>agent</th></tr></thead>
      <tbody>{points.map((p, i) => <tr key={i}><td>{p.date}</td><td>{p.baseline}%</td><td>{p.agent}%</td></tr>)}</tbody>
    </table>
    </>
  )
}
