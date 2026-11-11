import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brain, Pin, PinOff, Search, Trash2 } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { deleteMemory, getMemoryStats, listMemory, pinMemory, searchMemory } from '../api/client'
import type { MemoryItem } from '../api/types'
import { Chip, EmptyState, ErrorNote, PageHeader, Skeleton, Stat } from '../components/ui'
import { useHealth } from '../hooks/useHealth'
import { relativeTime } from '../lib/format'

// Charts load after the page paints, so the memories show up without waiting for them
const ImprovementPanel = lazy(() => import('../components/ImprovementPanel'))

const KINDS = [
  { id: 'all', label: 'everything' },
  { id: 'fix', label: 'lessons' },
  { id: 'failure', label: 'failures' },
]

function MemoryCard({ m, onPin, onDelete }: { m: MemoryItem; onPin: () => void; onDelete: () => void }) {
  const lesson = m.kind === 'fix'
  return (
    <article className={`panel flex flex-col p-4 ${m.pinned ? 'border-cyan shadow-[inset_3px_0_0_rgb(var(--cyan))]' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <Chip tone={lesson ? 'cyan' : 'danger'}>{lesson ? 'lesson' : 'failure'}</Chip>
        <div className="flex gap-1">
          {typeof m.similarity === 'number' && <Chip tone="cyan">{Math.round(m.similarity * 100)}% match</Chip>}
          <button type="button" onClick={onPin} className="btn-ghost p-1" aria-label={m.pinned ? 'Unpin memory' : 'Pin memory'}>
            {m.pinned ? <PinOff className="h-3.5 w-3.5" aria-hidden /> : <Pin className="h-3.5 w-3.5" aria-hidden />}
          </button>
          <button type="button" onClick={onDelete} className="btn-ghost p-1 hover:text-status-danger" aria-label="Forget this memory">
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>
      <p className="mt-3 line-clamp-3 text-sm text-ink">{m.task}</p>
      <div className="mt-3 space-y-1.5 border-t border-border pt-3 text-xs">
        <p className="break-words font-mono text-status-danger">{m.signature || m.error?.split('\n').slice(-1)[0] || 'unknown error'}</p>
        {lesson && m.lesson && <p className="text-ink-secondary"><span className="font-semibold text-cyan">what fixed it:</span> {m.lesson}</p>}
      </div>
      <div className="mt-auto flex justify-between pt-3 font-mono text-[10px] text-ink-muted">
        <span>{(m.seen ?? 1) > 1 ? `seen ${m.seen}× · ` : ''}recalled {m.uses ?? 0}×</span>
        <span>{relativeTime(m.timestamp)}</span>
      </div>
    </article>
  )
}

export default function MemoryExplorer() {
  const qc = useQueryClient()
  const { data: health } = useHealth()
  // Don't query memory until we know the server has it switched on
  const enabled = health?.memory_enabled === true
  const [kind, setKind] = useState('all')
  const [text, setText] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 400)
    return () => clearTimeout(id)
  }, [text])

  const stats = useQuery({ queryKey: ['memory-stats'], queryFn: getMemoryStats, enabled })
  const list = useQuery({ queryKey: ['memory', kind], queryFn: () => listMemory({ kind }), enabled: enabled && q.length < 3 })
  const search = useQuery({ queryKey: ['memory-search', q], queryFn: () => searchMemory(q, 0.3), enabled: enabled && q.length >= 3 })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['memory'] })
    qc.invalidateQueries({ queryKey: ['memory-search'] })
    qc.invalidateQueries({ queryKey: ['memory-stats'] })
  }
  const pin = useMutation({ mutationFn: (m: MemoryItem) => pinMemory(m.id, !m.pinned), onSuccess: refresh })
  const forget = useMutation({ mutationFn: (id: string) => deleteMemory(id), onSuccess: refresh })

  const items = q.length >= 3 ? search.data?.items ?? [] : list.data?.items ?? []
  const loading = q.length >= 3 ? search.isLoading : list.isLoading
  const error = list.error || search.error || stats.error

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="memory"
        title={<span className="flex items-center gap-2"><Brain className="h-6 w-6 text-cyan" aria-hidden /> What I've learned</span>}
        lede="Failures I couldn't fix and lessons from ones I did. Before every run I recall the closest matches so I don't repeat myself. You can pin what matters and delete what doesn't."
      />

      <Suspense fallback={<Skeleton className="h-72" />}>
        <ImprovementPanel />
      </Suspense>

      {!health ? (
        <Skeleton className="h-40" />
      ) : !enabled ? (
        <EmptyState icon={<Brain className="h-8 w-8" />} title="Memory is switched off on this server">
          Set MEMORY_ENABLED=true to let the agent learn across runs.
        </EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="memories" value={stats.data?.total ?? '—'} tone="cyan" />
            <Stat label="lessons" value={stats.data?.fixes ?? '—'} hint="fixed after failing" />
            <Stat label="failures" value={stats.data?.failures ?? '—'} hint="never solved" />
            <Stat label="times recalled" value={stats.data?.times_recalled ?? '—'} />
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex gap-1.5" role="group" aria-label="Filter memories">
              {KINDS.map((k) => (
                <button
                  key={k.id}
                  type="button"
                  aria-pressed={kind === k.id}
                  disabled={q.length >= 3}
                  onClick={() => setKind(k.id)}
                  className={`chip px-2.5 py-1 disabled:opacity-50 ${kind === k.id ? 'border-cyan bg-cyan text-ink-inverse' : 'border-border bg-surface text-ink-secondary'}`}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <label className="relative md:w-96">
              <span className="sr-only">Ask what the agent remembers</span>
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" aria-hidden />
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder="what do you remember about… regex? empty lists?" className="input pl-8 text-xs" />
            </label>
          </div>

          {error && <ErrorNote error={error} />}

          {loading ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-44" />)}</div>
          ) : items.length === 0 ? (
            <EmptyState icon={<Brain className="h-8 w-8" />} title={q ? 'Nothing comes to mind' : 'No memories yet'}>
              {q ? 'No stored memory is close to that.' : 'When a run fails, or fails and then gets fixed, I write down what happened here.'}
            </EmptyState>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {items.map((m) => (
                <MemoryCard
                  key={m.id}
                  m={m}
                  onPin={() => pin.mutate(m)}
                  onDelete={() => {
                    if (window.confirm('Forget this memory? Future runs will no longer see it.')) forget.mutate(m.id)
                  }}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
