import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface EvalDataPoint {
  date: string
  passAt1: number
  passAt5: number
  problems: number
}

interface EvalChartProps {
  data: EvalDataPoint[]
}

export default function EvalChart({ data }: EvalChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 rounded-xl border border-slate-800 bg-slate-900/30 flex items-center justify-center text-xs text-slate-500 italic">
        No historical evaluation runs recorded yet.
      </div>
    )
  }

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Accuracy Trend Over Time</h3>
          <p className="text-xs text-slate-400">pass@1 vs pass@5 comparison across evaluation milestones</p>
        </div>
      </div>

      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
            <XAxis
              dataKey="date"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickMargin={8}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                borderColor: '#334155',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                color: '#f8fafc',
              }}
              formatter={(value: any, name: any) => [
                `${Number(value).toFixed(1)}%`,
                name === 'passAt1' ? 'pass@1' : 'pass@5',
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: '0.75rem', paddingTop: '0.5rem' }}
              formatter={(value) => (value === 'passAt1' ? 'pass@1 Accuracy' : 'pass@5 Accuracy')}
            />
            <Line
              type="monotone"
              dataKey="passAt1"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#10b981' }}
              activeDot={{ r: 6 }}
            />
            <Line
              type="monotone"
              dataKey="passAt5"
              stroke="#6366f1"
              strokeWidth={2.5}
              strokeDasharray="4 4"
              dot={{ r: 4, fill: '#6366f1' }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
