import { useQuery } from '@tanstack/react-query'
import { CornerDownLeft, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listRuns } from '../api/client'
import { usePreferences } from '../hooks/usePreferences'
import { NAV_ITEMS } from './nav'

interface Command {
  id: string
  label: string
  hint: string
  run: () => void
}

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { isDark, update } = usePreferences()
  const [query, setQuery] = useState('')
  const [index, setIndex] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)

  const { data: recent } = useQuery({
    queryKey: ['palette-runs', query],
    queryFn: () => listRuns({ pageSize: 6, q: query.trim() || undefined }),
    enabled: open,
    staleTime: 5000,
  })

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) {
      setQuery('')
      setIndex(0)
      el.showModal()
    } else if (!open && el.open) el.close()
  }, [open])

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => {
      navigate(to)
      onClose()
    }
    const base: Command[] = [
      ...NAV_ITEMS.map((item) => ({ id: item.to, label: `Go to ${item.label}`, hint: item.to, run: go(item.to) })),
      { id: 'theme', label: isDark ? 'Switch to light ledger' : 'Switch to night shift', hint: 'theme', run: () => { update({ theme: isDark ? 'light' : 'dark' }); onClose() } },
    ]
    const runs: Command[] = (recent?.items ?? []).map((r) => ({
      id: r.run_id,
      label: r.task_description.slice(0, 80),
      hint: r.run_id,
      run: go(`/runs/${r.run_id}`),
    }))
    const q = query.trim().toLowerCase()
    return [...base.filter((c) => !q || c.label.toLowerCase().includes(q)), ...runs]
  }, [recent, query, isDark, navigate, onClose, update])

  const active = Math.min(index, Math.max(0, commands.length - 1))

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      aria-label="Command palette"
      className="mt-[12vh] w-[min(92vw,560px)] border border-border-strong bg-surface p-0 text-ink shadow-ledger backdrop:bg-ink/40"
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-4 w-4 text-ink-muted" aria-hidden />
        <input
          autoFocus
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIndex(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setIndex((i) => Math.min(i + 1, commands.length - 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)) }
            if (e.key === 'Enter') { e.preventDefault(); commands[active]?.run() }
          }}
          placeholder="Jump to a page or search runs…"
          className="w-full bg-transparent py-3 text-sm outline-none placeholder:text-ink-tertiary"
          role="combobox"
          aria-expanded="true"
          aria-controls="palette-list"
          aria-activedescendant={commands[active] ? `cmd-${commands[active].id}` : undefined}
        />
      </div>
      <ul id="palette-list" role="listbox" className="max-h-80 overflow-auto py-1">
        {commands.length === 0 && <li className="px-4 py-6 text-center text-sm text-ink-muted">Nothing matches.</li>}
        {commands.map((cmd, i) => (
          <li
            key={cmd.id}
            id={`cmd-${cmd.id}`}
            role="option"
            aria-selected={i === active}
            onMouseEnter={() => setIndex(i)}
            onClick={cmd.run}
            className={`flex cursor-pointer items-center justify-between gap-3 px-4 py-2 text-sm ${i === active ? 'bg-accent-subtle text-ink' : 'text-ink-secondary'}`}
          >
            <span className="truncate">{cmd.label}</span>
            <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] text-ink-muted">
              {cmd.hint}
              {i === active && <CornerDownLeft className="h-3 w-3" aria-hidden />}
            </span>
          </li>
        ))}
      </ul>
    </dialog>
  )
}
