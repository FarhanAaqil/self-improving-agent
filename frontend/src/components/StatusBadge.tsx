import { AlertTriangle, CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const norm = status.toLowerCase()

  if (norm === 'success') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 ${
          size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
        }`}
      >
        <CheckCircle2 className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        <span>Success</span>
      </span>
    )
  }

  if (norm === 'failed' || norm === 'max_retries_exceeded') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30 ${
          size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
        }`}
      >
        <XCircle className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        <span>{norm === 'max_retries_exceeded' ? 'Max Retries' : 'Failed'}</span>
      </span>
    )
  }

  if (norm === 'running' || norm === 'started') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 ${
          size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
        }`}
      >
        <Loader2 className={`animate-spin ${size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'}`} />
        <span>Running</span>
      </span>
    )
  }

  if (norm === 'generated') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full font-medium bg-sky-500/15 text-sky-300 border border-sky-500/30 ${
          size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
        }`}
      >
        <Clock className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        <span>Generated</span>
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium bg-slate-800 text-slate-300 border border-slate-700 ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      }`}
    >
      <AlertTriangle className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
      <span>{status}</span>
    </span>
  )
}
