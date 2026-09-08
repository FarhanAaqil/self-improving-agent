import { useParams } from 'react-router-dom'

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold tracking-tight text-slate-100">Run Detail</h2>
      <p className="text-slate-400 font-mono text-sm">Viewing run ID: {runId}</p>
    </div>
  )
}
