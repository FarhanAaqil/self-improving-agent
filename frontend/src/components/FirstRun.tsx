import { CheckCircle2, Circle, X } from 'lucide-react'
import { useState } from 'react'

export const STARTER_TASK =
  'Write a function roman_to_int(s) that converts a Roman numeral string like "MCMXCIV" to an integer. ' +
  'Raise ValueError for empty strings or invalid characters.'

function dismissedKey(userId: string) {
  return `first-run-done:${userId}`
}

function readDismissed(userId: string): boolean {
  try {
    return localStorage.getItem(dismissedKey(userId)) === '1'
  } catch {
    return false
  }
}

/**
 * A new account's first three steps, in place on the Workbench: add a key, run a starter
 * task, see it verified. Disappears once done (or dismissed), remembered per browser.
 */
export default function FirstRun({
  userId,
  hasKey,
  needsKey,
  ranOnce,
  verifiedOnce,
  onRunStarter,
}: {
  userId: string
  hasKey: boolean
  needsKey: boolean
  ranOnce: boolean
  verifiedOnce: boolean
  onRunStarter: () => void
}) {
  const [dismissed, setDismissed] = useState(() => readDismissed(userId))
  if (dismissed || verifiedOnce) return null

  const dismiss = () => {
    try {
      localStorage.setItem(dismissedKey(userId), '1')
    } catch {
      // storage blocked; it just comes back next visit
    }
    setDismissed(true)
  }

  const steps = [
    { done: !needsKey || hasKey, title: 'Add your Groq key', text: needsKey ? 'Free plans run on your own key. Paste it in the box above.' : 'Your plan includes our key, so this step is done.' },
    { done: ranOnce, title: 'Run the starter task', text: 'A Roman numeral converter with edge cases, so there is something for the tests to catch.' },
    { done: verifiedOnce, title: 'Watch it test, fix and pass', text: 'Every step streams in. If a test fails, it reads the traceback and repairs the code.' },
  ]
  const next = steps.findIndex((s) => !s.done)

  return (
    <section className="panel p-5" aria-labelledby="first-run-title">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="eyebrow">getting started</div>
          <h2 id="first-run-title" className="mt-1 font-mono text-base font-bold">Your first verified run, in three steps</h2>
        </div>
        <button type="button" onClick={dismiss} className="btn-ghost px-2 py-1" aria-label="Hide getting started">
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
      <ol className="mt-4 space-y-3">
        {steps.map((step, i) => (
          <li key={step.title} className="flex gap-3">
            {step.done
              ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-status-success" aria-label="done" />
              : <Circle className={`mt-0.5 h-4 w-4 shrink-0 ${i === next ? 'text-accent' : 'text-ink-tertiary'}`} aria-label="to do" />}
            <div className="min-w-0 flex-1">
              <div className={`text-sm font-semibold ${step.done ? 'text-ink-secondary line-through' : 'text-ink'}`}>{step.title}</div>
              <div className="text-xs text-ink-secondary">{step.text}</div>
              {i === 1 && i === next && (
                <button type="button" onClick={onRunStarter} className="btn-primary mt-2 px-2.5 py-1 text-xs">run the starter task</button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
