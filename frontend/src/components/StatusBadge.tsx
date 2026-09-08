import { AlertTriangle, CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const norm = status.toLowerCase()

  const baseClasses = `inline-flex items-center gap-1.5 font-sans font-medium bg-surface border border-border border-l-[3px] rounded-[2px] transition-colors ${
    size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
  }`

  if (norm === 'success') {
    return (
      <span className={`${baseClasses} border-l-status-success text-ink`}>
        <CheckCircle2 className="h-3.5 w-3.5 text-status-success shrink-0" />
        <span>Success</span>
      </span>
    )
  }

  if (norm === 'failed' || norm === 'max_retries_exceeded') {
    return (
      <span className={`${baseClasses} border-l-status-danger text-ink`}>
        <XCircle className="h-3.5 w-3.5 text-status-danger shrink-0" />
        <span>{norm === 'max_retries_exceeded' ? 'Max Retries' : 'Failed'}</span>
      </span>
    )
  }

  if (norm === 'running' || norm === 'started') {
    return (
      <span className={`${baseClasses} border-l-accent text-ink`}>
        <Loader2 className="h-3.5 w-3.5 text-accent animate-spin shrink-0" />
        <span>Running</span>
      </span>
    )
  }

  if (norm === 'generated') {
    return (
      <span className={`${baseClasses} border-l-status-warning text-ink`}>
        <Clock className="h-3.5 w-3.5 text-status-warning shrink-0" />
        <span>Generated</span>
      </span>
    )
  }

  return (
    <span className={`${baseClasses} border-l-ink-tertiary text-ink-secondary`}>
      <AlertTriangle className="h-3.5 w-3.5 text-ink-tertiary shrink-0" />
      <span>{status}</span>
    </span>
  )
}
