import { Check, Loader2, X } from 'lucide-react'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const norm = status.toLowerCase()

  const isSm = size === 'sm'
  const py = isSm ? 'py-0.5' : 'py-1'
  const px = isSm ? 'px-2' : 'px-2.5'
  const textSz = isSm ? 'text-[11px]' : 'text-xs'

  if (norm === 'success') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-mono font-medium border border-status-success/50 bg-status-success-subtle text-status-success ${px} ${py} ${textSz}`}
      >
        <span className="text-[10px] font-bold">⌐</span>
        <Check className="h-3 w-3 stroke-[2.5]" />
        <span>passed</span>
        <span className="text-[10px] font-bold">¬</span>
      </span>
    )
  }

  if (norm === 'failed' || norm === 'max_retries_exceeded') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-mono font-medium border border-status-danger/50 bg-status-danger-subtle text-status-danger ${px} ${py} ${textSz}`}
      >
        <span className="text-[10px] font-bold">⌐</span>
        <X className="h-3 w-3 stroke-[2.5]" />
        <span>{norm === 'max_retries_exceeded' ? 'max retries' : 'failed'}</span>
        <span className="text-[10px] font-bold">¬</span>
      </span>
    )
  }

  if (norm === 'running' || norm === 'started') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-mono font-semibold border border-accent/50 bg-accent-subtle text-accent ${px} ${py} ${textSz}`}
      >
        <span className="text-[10px] font-bold">⌐</span>
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>running</span>
        <span className="text-[10px] font-bold">¬</span>
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-ink-secondary border border-border bg-surface-sunken ${px} ${py} ${textSz}`}
    >
      <span className="text-[10px] font-bold">⌐</span>
      <span>{status}</span>
      <span className="text-[10px] font-bold">¬</span>
    </span>
  )
}
