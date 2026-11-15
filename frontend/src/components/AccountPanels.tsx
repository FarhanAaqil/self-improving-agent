import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ApiError, changePassword, createApiKey, listApiKeys, revokeApiKey } from '../api/client'
import type { AccountUser } from '../api/types'
import { copyText } from '../lib/clipboard'
import { relativeTime } from '../lib/format'
import { ErrorNote, Panel } from './ui'

export function ProfilePanel({ user }: { user: AccountUser }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null)
  const change = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setNote({ ok: true, text: 'Password changed. Other devices were signed out.' })
    },
    onError: (err) => setNote({ ok: false, text: err instanceof ApiError ? err.message : 'That didn’t work.' }),
  })

  return (
    <Panel title="profile">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[8rem_1fr]">
        <dt className="text-ink-muted">email</dt>
        <dd className="font-mono text-ink">{user.email}</dd>
        <dt className="text-ink-muted">account id</dt>
        <dd className="font-mono text-ink-secondary">{user.user_id}</dd>
        <dt className="text-ink-muted">member since</dt>
        <dd className="text-ink-secondary">{user.created_at ? relativeTime(user.created_at) : '—'}</dd>
      </dl>
      <form
        className="mt-5 grid gap-3 border-t border-border pt-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault()
          setNote(null)
          change.mutate()
        }}
      >
        <label className="block">
          <span className="eyebrow">current password</span>
          <input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} className="input mt-1" />
        </label>
        <label className="block">
          <span className="eyebrow">new password</span>
          <input type="password" autoComplete="new-password" minLength={10} required value={next} onChange={(e) => setNext(e.target.value)} className="input mt-1" />
        </label>
        <button type="submit" className="btn-secondary" disabled={change.isPending}>change password</button>
      </form>
      {note && <p role="status" className={`mt-2 text-xs ${note.ok ? 'text-status-success' : 'text-status-danger'}`}>{note.text}</p>}
    </Panel>
  )
}

export function ApiKeysPanel() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [fresh, setFresh] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const keys = useQuery({ queryKey: ['api-keys'], queryFn: listApiKeys })
  const create = useMutation({
    mutationFn: () => createApiKey(name),
    onSuccess: (res) => {
      setFresh(res.key)
      setName('')
      qc.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })
  const revoke = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
  const active = (keys.data?.items ?? []).filter((k) => !k.revoked_at)

  return (
    <Panel title="api keys">
      <p className="text-sm text-ink-secondary">
        For scripts and CI. Send one as <code className="bg-surface-sunken px-1 font-mono text-xs">X-API-Key</code> or a Bearer token;
        runs land in your own workspace. Only a hash is stored, so a key is shown once.
      </p>

      {fresh && (
        <div className="mt-4 border border-status-success/40 bg-status-success-subtle p-3">
          <div className="text-sm font-semibold text-status-success">Copy this key now. It won’t be shown again.</div>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 break-all bg-surface px-2 py-1.5 font-mono text-xs text-ink" data-testid="new-api-key">{fresh}</code>
            <button
              type="button"
              className="btn-secondary px-2 py-1"
              onClick={() => copyText(fresh).then(() => setCopied(true))}
              aria-label="Copy API key"
            >
              <Copy className="h-3.5 w-3.5" aria-hidden /> {copied ? 'copied' : 'copy'}
            </button>
          </div>
          <button type="button" className="mt-2 text-xs text-ink-secondary underline" onClick={() => { setFresh(null); setCopied(false) }}>
            I’ve saved it
          </button>
        </div>
      )}

      <form
        className="mt-4 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault()
          create.mutate()
        }}
      >
        <label className="flex-1">
          <span className="sr-only">Key name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="name it, e.g. laptop script" className="input" />
        </label>
        <button type="submit" className="btn-secondary" disabled={create.isPending}>
          <KeyRound className="h-3.5 w-3.5" aria-hidden /> create key
        </button>
      </form>
      {create.isError && <div className="mt-2"><ErrorNote error={create.error} /></div>}

      <ul className="mt-4 divide-y divide-border border-y border-border" aria-label="Your API keys">
        {active.length === 0 && <li className="py-3 text-sm text-ink-muted">No keys yet.</li>}
        {active.map((k) => (
          <li key={k.key_id} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <div className="truncate text-sm text-ink">{k.name}</div>
              <div className="font-mono text-[11px] text-ink-muted">
                {k.prefix}… · created {relativeTime(k.created_at)} · {k.last_used_at ? `used ${relativeTime(k.last_used_at)}` : 'never used'}
              </div>
            </div>
            <button type="button" className="btn-ghost px-2 py-1 text-status-danger" onClick={() => revoke.mutate(k.key_id)} aria-label={`Revoke ${k.name}`}>
              <Trash2 className="h-3.5 w-3.5" aria-hidden /> revoke
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
