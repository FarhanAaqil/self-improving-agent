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
      <div className="h-64 border border-border bg-surface flex items-center justify-center text-xs font-mono text-ink-tertiary">
        no historical evaluation runs recorded yet.
      </div>
    )
  }

  return (
    <div className="bg-surface border border-border p-5 space-y-3">
      <div className="flex items-center justify-between border-b border-border pb-2">
        <div>
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-ink">
            benchmark progress over time
          </h3>
          <p className="text-xs text-ink-secondary mt-0.5">
            pass@1 accuracy across benchmark iterations
          </p>
        </div>
      </div>

      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#CBD3C7" opacity={0.6} />
            <XAxis
              dataKey="date"
              stroke="#52655A"
              fontSize={11}
              tickLine={false}
              tickMargin={8}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#52655A"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#FFFFFF',
                borderColor: '#CBD3C7',
                borderRadius: '0px',
                fontSize: '11px',
                color: '#10241C',
                fontFamily: 'monospace',
                boxShadow: 'none',
              }}
              formatter={(value: any, name: any) => [
                `${Number(value).toFixed(1)}%`,
                name === 'passAt1' ? 'pass@1' : 'pass@5',
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '0.5rem', fontFamily: 'monospace' }}
              formatter={(value) => (value === 'passAt1' ? 'pass@1 accuracy' : 'pass@5 accuracy')}
            />
            {/* Primary line: Calibration Orange #FF5A1F */}
            <Line
              type="monotone"
              dataKey="passAt1"
              stroke="#FF5A1F"
              strokeWidth={2}
              dot={{ r: 3, fill: '#FF5A1F' }}
              activeDot={{ r: 5 }}
            />
            {/* Secondary comparison line: Deep Teal #0E7C86 */}
            <Line
              type="monotone"
              dataKey="passAt5"
              stroke="#0E7C86"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={{ r: 2.5, fill: '#0E7C86' }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
