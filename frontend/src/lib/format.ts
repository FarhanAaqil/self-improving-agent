export function relativeTime(iso?: string | null): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

export function duration(ms?: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

export function score10(score?: number | null): string {
  return score === null || score === undefined ? '—' : (score * 10).toFixed(1)
}

export function pct(value?: number | null, digits = 0): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`
}

export function compactNumber(n?: number | null): string {
  if (!n) return '0'
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

export function statusMeta(status?: string | null): { label: string; tone: 'success' | 'danger' | 'warning' | 'accent' | 'muted' } {
  switch (status) {
    case 'success':
      return { label: 'verified', tone: 'success' }
    case 'max_retries_exceeded':
      return { label: 'out of attempts', tone: 'danger' }
    case 'early_stopped':
      return { label: 'stopped early', tone: 'warning' }
    case 'failed':
      return { label: 'failed', tone: 'danger' }
    case 'running':
      return { label: 'running', tone: 'accent' }
    case 'queued':
      return { label: 'queued', tone: 'accent' }
    case 'generated':
      return { label: 'generated', tone: 'muted' }
    default:
      return { label: status ?? 'unknown', tone: 'muted' }
  }
}
