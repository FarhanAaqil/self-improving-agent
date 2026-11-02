import { Check, Minus, X } from 'lucide-react'
import type { Stage } from '../lib/narrate'

/** Viewfinder-bracket pipeline. Each stage carries an icon and a word, not just a color. */
export default function Stepper({ stages }: { stages: Stage[] }) {
  return (
    <ol className="panel grid grid-cols-3 gap-y-4 px-3 py-4 sm:grid-cols-6" aria-label="Pipeline progress">
      {stages.map((stage, i) => {
        const tone =
          stage.state === 'active' ? 'text-accent border-accent'
            : stage.state === 'passed' ? 'text-status-success border-status-success'
              : stage.state === 'failed' ? 'text-status-danger border-status-danger'
                : 'text-ink-tertiary border-border-strong'
        return (
          <li key={stage.id} className="relative flex flex-col items-center text-center" aria-current={stage.state === 'active' ? 'step' : undefined}>
            {i > 0 && (
              <span
                className={`absolute right-1/2 top-[18px] hidden h-px w-full -translate-x-[22px] sm:block ${
                  stage.state === 'pending' ? 'bg-border' : 'bg-border-strong'
                }`}
                aria-hidden
              />
            )}
            <span className={`relative z-10 flex h-9 w-9 items-center justify-center bg-surface ${tone} ${stage.state === 'active' ? 'animate-breathe' : ''}`}>
              {(['top-0 left-0 border-t-2 border-l-2', 'top-0 right-0 border-t-2 border-r-2', 'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-b-2 border-r-2'] as const).map((pos) => (
                <span key={pos} className={`absolute h-2.5 w-2.5 border-current ${pos}`} aria-hidden />
              ))}
              {stage.state === 'passed' ? <Check className="h-4 w-4" strokeWidth={2.5} aria-hidden />
                : stage.state === 'failed' ? <X className="h-4 w-4" strokeWidth={2.5} aria-hidden />
                  : stage.state === 'skipped' ? <Minus className="h-4 w-4" aria-hidden />
                    : <span className="font-mono text-xs font-bold">0{i + 1}</span>}
            </span>
            <span className={`mt-2 font-mono text-xs font-semibold ${stage.state === 'pending' ? 'text-ink-secondary' : tone.split(' ')[0]}`}>
              {stage.label}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              {stage.state === 'active' ? 'working' : stage.state === 'pending' ? stage.hint : stage.state}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
