import { useMemo } from 'react'
import { diffLines, diffStats } from '../lib/diff'

export default function DiffView({ before, after, beforeLabel, afterLabel }: {
  before: string
  after: string
  beforeLabel: string
  afterLabel: string
}) {
  const lines = useMemo(() => diffLines(before, after), [before, after])
  const { added, removed } = diffStats(lines)

  return (
    <div className="border border-border bg-surface-sunken">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-1.5 font-mono text-[11px]">
        <span className="text-ink-muted">
          {beforeLabel} → {afterLabel}
        </span>
        <span>
          <span className="text-status-success">+{added}</span>{' '}
          <span className="text-status-danger">−{removed}</span>
        </span>
      </div>
      <pre className="max-h-[28rem] overflow-auto py-2 font-mono text-[12.5px] leading-6" tabIndex={0}>
        {added + removed === 0 && <div className="px-3 text-ink-muted">No changes between these attempts.</div>}
        {lines.map((line, i) => (
          <div
            key={i}
            className={`flex px-3 ${
              line.kind === 'add'
                ? 'bg-status-success-subtle text-status-success'
                : line.kind === 'remove'
                  ? 'bg-status-danger-subtle text-status-danger'
                  : 'text-ink-secondary'
            }`}
          >
            <span className="w-4 shrink-0 select-none" aria-hidden>
              {line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : ' '}
            </span>
            <span className="sr-only">{line.kind === 'add' ? 'added' : line.kind === 'remove' ? 'removed' : ''}</span>
            <span className="whitespace-pre">{line.text || ' '}</span>
          </div>
        ))}
      </pre>
    </div>
  )
}
