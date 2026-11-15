import { Play, RotateCcw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ApiError, startDemo } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import { deriveStages, narrate, type Mood } from '../lib/narrate'
import Stepper from './Stepper'
import VerifiedStamp from './VerifiedStamp'

const DOT: Record<Mood, string> = {
  thinking: 'bg-accent',
  memory: 'bg-cyan',
  success: 'bg-status-success',
  failure: 'bg-status-danger',
  neutral: 'bg-border-strong',
}

/**
 * A real run anyone can watch: the scripted model (so nobody's tokens are spent), the real
 * Docker sandbox, spec tests, a deliberate first failure, the diagnosis and the repair.
 */
export default function LiveDemo() {
  const [run, setRun] = useState<{ id: string; share: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const stream = useRunStream(run?.id, '/demo/runs')

  const story = useMemo(() => stream.events.map(narrate).filter((s) => s !== null), [stream.events])
  const stages = useMemo(
    () => deriveStages(stream.events, stream.finished ? stream.finalStatus ?? undefined : undefined),
    [stream.events, stream.finished, stream.finalStatus],
  )
  const verified = stream.finished && stream.finalStatus === 'success'
  const passedOn = stream.events.find((e) => e.type === 'verified')?.payload.attempt as number | undefined

  const start = async () => {
    setStarting(true)
    setError(null)
    try {
      const res = await startDemo()
      setRun({ id: res.run_id, share: res.share_url })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The demo couldn’t start. Try again in a moment.')
    } finally {
      setStarting(false)
    }
  }

  return (
    <section className="panel overflow-hidden shadow-ledger" aria-labelledby="demo-title">
      <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="demo-title" className="font-mono text-sm font-bold">Watch a live run</h2>
          <p className="text-xs text-ink-secondary">
            Task: <code className="font-mono">Write add(a, b) returning the sum</code>. A scripted model, so it gets attempt 1 wrong on purpose. The sandbox is real.
          </p>
        </div>
        <button type="button" onClick={start} disabled={starting || (Boolean(run) && !stream.finished)} className="btn-primary shrink-0">
          {run && stream.finished ? <RotateCcw className="h-3.5 w-3.5" aria-hidden /> : <Play className="h-3.5 w-3.5 fill-current" aria-hidden />}
          {starting ? 'starting…' : run ? (stream.finished ? 'run it again' : 'running…') : 'start the demo'}
        </button>
      </div>

      {error && <p role="alert" className="border-b border-status-danger/30 bg-status-danger-subtle px-5 py-2 text-sm text-status-danger">{error}</p>}

      <div className="space-y-4 p-5">
        <Stepper stages={stages} />
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <ol className="max-h-72 space-y-2 overflow-y-auto" aria-live="polite" aria-label="What the agent is doing">
            {!run && <li className="text-sm text-ink-muted">Press start to watch every step stream in.</li>}
            {story.map((line) => (
              <li key={line.id} className="flex animate-rise-in gap-3">
                <span className={`mt-1.5 h-2 w-2 shrink-0 ${DOT[line.mood]}`} aria-hidden />
                <div className="min-w-0">
                  <p className="text-sm text-ink">{line.text}</p>
                  {line.detail && <p className="mt-0.5 break-words font-mono text-[11px] text-ink-muted">{line.detail}</p>}
                </div>
              </li>
            ))}
          </ol>
          {verified && (
            <div className="flex flex-col items-center gap-3">
              <VerifiedStamp status="verified" attempt={passedOn} />
              {run && <a href={run.share} className="font-mono text-xs text-accent-ink underline">see the certificate</a>}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
