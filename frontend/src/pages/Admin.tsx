import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Search, ShieldOff, ShieldCheck as ShieldOn } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminBackupNow, adminBackups, adminListUsers, adminSetActive, adminSetPlan } from '../api/client'
import { Chip, EmptyState, ErrorNote, PageHeader, Panel, Skeleton } from '../components/ui'
import { useSession } from '../hooks/useSession'
import { compactNumber, relativeTime } from '../lib/format'

/** Operators and ADMIN_EMAILS accounts: every user, their plan and usage, and a disable switch. */
export default function Admin() {
  const { isOperator, isLoading } = useSession()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(id)
  }, [search])

  const users = useQuery({
    queryKey: ['admin-users', q],
    queryFn: () => adminListUsers(q),
    enabled: isOperator,
    placeholderData: keepPreviousData,
  })
  const backups = useQuery({ queryKey: ['admin-backups'], queryFn: adminBackups, enabled: isOperator })
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin-users'] })
  const toggle = useMutation({ mutationFn: (v: { id: string; active: boolean }) => adminSetActive(v.id, v.active), onSuccess: refresh })
  const plan = useMutation({ mutationFn: (v: { id: string; plan: string; days?: number }) => adminSetPlan(v.id, v.plan, v.days), onSuccess: refresh })
  const backupNow = useMutation({ mutationFn: adminBackupNow, onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-backups'] }) })

  if (isLoading) return <Skeleton className="h-64" />
  if (!isOperator) return <EmptyState title="Admins only">This page is for the people who run this server.</EmptyState>

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="admin" title="Accounts" lede="Plans, today's usage and the disable switch. A disabled account is signed out everywhere and its API keys stop working." />

      <label className="relative block md:w-80">
        <span className="sr-only">Search accounts</span>
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" aria-hidden />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="email or user id" className="input pl-8 font-mono text-xs" />
      </label>

      {(users.error || toggle.error || plan.error) && <ErrorNote error={users.error || toggle.error || plan.error} />}

      {users.isLoading ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Accounts</caption>
            <thead className="border-b border-border bg-surface-sunken font-mono text-[11px] uppercase tracking-wider text-ink-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">account</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">plan</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">runs today</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">all runs</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">our tokens today</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">joined</th>
                <th scope="col" className="px-3 py-2 text-right font-medium"><span className="sr-only">actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(users.data?.items ?? []).map((u) => (
                <tr key={u.user_id} className={u.active ? '' : 'opacity-60'}>
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs text-ink">{u.email}</div>
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {!u.active && <Chip tone="danger">disabled</Chip>}
                      {!u.verified && <Chip tone="warning">unverified</Chip>}
                      {u.new_account && <Chip tone="accent">new</Chip>}
                      {u.admin && <Chip tone="cyan">admin</Chip>}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs">{u.effective_plan}</span>
                    {u.paid_until && u.effective_plan !== 'free' && <div className="text-[11px] text-ink-muted">until {new Date(u.paid_until).toLocaleDateString()}</div>}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{u.runs_today}</td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{u.runs_total}</td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{compactNumber(u.server_tokens_today)}</td>
                  <td className="px-3 py-2 text-right font-mono text-[11px] text-ink-muted">{relativeTime(u.created_at)}</td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end gap-1">
                      <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => plan.mutate({ id: u.user_id, plan: 'pro', days: 31 })} aria-label={`Give ${u.email} 31 days of Pro`}>
                        +31d pro
                      </button>
                      {u.effective_plan !== 'free' && (
                        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => plan.mutate({ id: u.user_id, plan: 'free' })} aria-label={`Move ${u.email} to Free`}>
                          to free
                        </button>
                      )}
                      <button
                        type="button"
                        className={`btn-ghost px-2 py-1 text-xs ${u.active ? 'text-status-danger' : 'text-status-success'}`}
                        onClick={() => toggle.mutate({ id: u.user_id, active: !u.active })}
                        aria-label={`${u.active ? 'Disable' : 'Enable'} ${u.email}`}
                      >
                        {u.active ? <ShieldOff className="h-3.5 w-3.5" aria-hidden /> : <ShieldOn className="h-3.5 w-3.5" aria-hidden />}
                        {u.active ? 'disable' : 'enable'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.data?.items.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-ink-muted">No accounts match.</td></tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-border px-3 py-2 font-mono text-[11px] text-ink-muted">{users.data?.total ?? 0} accounts</div>
        </div>
      )}

      <Panel
        title="backups"
        actions={
          <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={() => backupNow.mutate()} disabled={backupNow.isPending || !backups.data?.dir_configured}>
            <Archive className="h-3.5 w-3.5" aria-hidden /> {backupNow.isPending ? 'backing up…' : 'back up now'}
          </button>
        }
      >
        {!backups.data?.dir_configured ? (
          <p className="text-sm text-ink-secondary">Set <code className="font-mono">BACKUP_DIR</code> to turn on nightly backups.</p>
        ) : (
          <ul className="divide-y divide-border font-mono text-xs">
            {(backups.data?.items ?? []).slice(0, 10).map((b) => (
              <li key={b.name} className="flex justify-between py-1.5"><span>{b.name}</span><span className="text-ink-muted">{compactNumber(b.bytes)} B</span></li>
            ))}
            {backups.data?.items.length === 0 && <li className="py-1.5 text-ink-muted">None yet.</li>}
          </ul>
        )}
        {backupNow.isError && <div className="mt-2"><ErrorNote error={backupNow.error} /></div>}
      </Panel>
    </div>
  )
}
