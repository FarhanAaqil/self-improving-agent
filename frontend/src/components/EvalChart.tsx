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
      <div className="h-64 rounded border border-border bg-surface flex items-center justify-center text-xs text-ink-tertiary">
        No historical evaluation runs recorded yet.
      </div>
    )
  }

  return (
    <div className="bg-surface border border-border rounded p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-semibold text-ink">Benchmark progress over time</h3>
          <p className="text-xs text-ink-secondary">pass@1 accuracy across benchmark iterations</p>
        </div>
      </div>

      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E1E4EA" opacity={0.8} />
            <XAxis
              dataKey="date"
              stroke="#8891A3"
              fontSize={11}
              tickLine={false}
              tickMargin={8}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#8891A3"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#FFFFFF',
                borderColor: '#E1E4EA',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#10182B',
                boxShadow: 'none',
              }}
              formatter={(value: any, name: any) => [
                `${Number(value).toFixed(1)}%`,
                name === 'passAt1' ? 'pass@1' : 'pass@5',
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '0.5rem' }}
              formatter={(value) => (value === 'passAt1' ? 'pass@1 accuracy' : 'pass@5 accuracy')}
            />
            <Line
              type="monotone"
              dataKey="passAt1"
              stroke="#2E4CE0"
              strokeWidth={2}
              dot={{ r: 3, fill: '#2E4CE0' }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="passAt5"
              stroke="#4A5468"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={{ r: 2.5, fill: '#4A5468' }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
