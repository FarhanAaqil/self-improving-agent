import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2, ShieldAlert, ShieldCheck, Swords } from 'lucide-react'
import { useState } from 'react'
import { getSandboxConfig, listAttacks, runAttack } from '../api/client'
import type { AttackResult } from '../api/types'
import { Chip, ErrorNote, PageHeader, Panel, Skeleton } from '../components/ui'

// What each docker flag buys you, in plain words
const FLAG_NOTES: [string, string][] = [
  ['--network', 'No network at all: nothing can be sent out.'],
  ['--memory', 'Hard memory cap; going over gets the process killed.'],
  ['--memory-swap', 'Same as the memory cap, so swap is not an escape hatch.'],
  ['--cpus', 'CPU throttle against miners and runaway loops.'],
  ['--pids-limit', 'Process limit; fork bombs hit a wall.'],
  ['--read-only', 'The whole filesystem is read-only.'],
  ['--tmpfs', 'Only /tmp is writable, and nothing there can be executed.'],
  ['--cap-drop', 'Every Linux capability removed.'],
  ['--security-opt', 'setuid binaries cannot raise privileges.'],
  ['--user', 'Runs as nobody, never root.'],
  ['--ulimit', 'Caps on open files and file size.'],
  ['-i', 'Code arrives over stdin; no host folder is mounted.'],
]

function flagPairs(fullCommand: string[], image: string): [string, string][] {
  // Docker's own flags end at the image name; what follows is python's command line
  const end = fullCommand.indexOf(image)
  const command = end === -1 ? fullCommand : fullCommand.slice(0, end)
  const pairs: [string, string][] = []
  for (let i = 0; i < command.length; i++) {
    const part = command[i]
    if (!part.startsWith('-')) continue
    const next = command[i + 1]
    const hasValue = next !== undefined && !next.startsWith('-') && part !== '-i' && part !== '--rm' && part !== '--read-only'
    pairs.push([part, hasValue ? next : ''])
    if (hasValue) i++
  }
  return pairs
}

export default function Security() {
  const config = useQuery({ queryKey: ['sandbox-config'], queryFn: getSandboxConfig })
  const attacks = useQuery({ queryKey: ['attacks'], queryFn: listAttacks })
  const [results, setResults] = useState<Record<string, AttackResult>>({})
  const attack = useMutation({
    mutationFn: runAttack,
    onSuccess: (r) => setResults((prev) => ({ ...prev, [r.name]: r })),
  })

  const flags = config.data ? flagPairs(config.data.command, config.data.image).filter(([f]) => !['--name', '-e', '-w', '--rm'].includes(f)) : []

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="security"
        title="Untrusted code, locked in a box"
        lede="Everything a model writes is treated as hostile. This page reads the sandbox settings straight from the server, and the attacks below run for real against it."
      />

      {/* Warnings appear above the panels, so show nothing until both requests settle */}
      {(config.isLoading || attacks.isLoading) ? <Skeleton className="h-[36rem]" /> : (<>
      {config.data && !config.data.docker_available && (
        <ErrorNote error={new Error('Docker is not available on this server, so code execution is refused entirely (there is no unsafe fallback).')} />
      )}
      {config.data?.host_fallback_enabled && (
        <ErrorNote error={new Error('Warning: ALLOW_UNSAFE_HOST_SUBPROCESS is on. If Docker goes away, code would run on the host. Never enable this on a shared server.')} />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="the exact sandbox" icon={<ShieldCheck className="h-3.5 w-3.5 text-status-success" aria-hidden />}>
          {config.isLoading ? (
            <Skeleton className="h-72" />
          ) : config.data ? (
            <>
              <p className="mb-3 font-mono text-[11px] text-ink-muted">
                image {config.data.image} · {config.data.timeout_seconds}s wall-clock limit, enforced from the host
              </p>
              <ul className="divide-y divide-border">
                {flags.map(([flag, value], i) => {
                  const note = FLAG_NOTES.find(([f]) => f === flag)?.[1]
                  return (
                    <li key={`${flag}-${i}`} className="py-2">
                      <code className="font-mono text-xs font-bold text-cyan">{flag}{value ? ` ${value}` : ''}</code>
                      {note && <p className="text-xs text-ink-secondary">{note}</p>}
                    </li>
                  )
                })}
              </ul>
            </>
          ) : (
            <ErrorNote error={config.error} />
          )}
        </Panel>

        <Panel title="try to break it" icon={<Swords className="h-3.5 w-3.5 text-accent" aria-hidden />} bodyClassName="p-0">
          <p className="border-b border-border px-4 py-3 text-sm text-ink-secondary">
            Each button runs a real attack script inside the sandbox. These are the same scripts CI runs on every change.
          </p>
          <ul className="divide-y divide-border">
            {(attacks.data?.items ?? []).map((a) => {
              const r = results[a.name]
              const busy = attack.isPending && attack.variables === a.name
              return (
                <li key={a.name} className="flex items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs font-bold text-ink">{a.title}</div>
                    <p className="text-xs text-ink-secondary">{a.description}</p>
                    {r && (
                      <p className={`mt-1.5 flex items-start gap-1.5 font-mono text-[11px] ${r.blocked ? 'text-status-success' : 'text-status-danger'}`}>
                        {r.blocked ? <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /> : <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />}
                        <span>{r.blocked ? 'Blocked' : 'Not blocked'}: {r.verdict}</span>
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {r && <Chip tone={r.blocked ? 'success' : 'danger'}>{r.latency_ms}ms</Chip>}
                    <button
                      type="button"
                      onClick={() => attack.mutate(a.name)}
                      disabled={busy || !config.data?.docker_available}
                      className="btn-secondary px-2.5 py-1"
                    >
                      {busy ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : 'launch'}
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
          {attack.isError && <div className="p-3"><ErrorNote error={attack.error} /></div>}
        </Panel>
      </div>

      </>)}

      <Panel title="what this does not protect against">
        <ul className="list-disc space-y-2 pl-5 text-sm text-ink-secondary">
          <li><strong className="text-ink">Kernel zero-days.</strong> Docker shares the host kernel. For hostile multi-tenant use, run the sandbox under gVisor (runsc), Kata, or a microVM provider.</li>
          <li><strong className="text-ink">The Docker socket.</strong> The API talks to Docker to start containers. The compose setup routes that through a socket proxy that refuses exec, volumes, networks, builds and system calls, and the API itself runs as a non-root user with no socket. A proxy still can't inspect what a container create asks for, so treat the API host as trusted and keep it on its own machine.</li>
          <li><strong className="text-ink">Correctness.</strong> Passing spec tests means the code does what the tests check. The tests are written by a model too, so read anything you ship.</li>
          <li><strong className="text-ink">Prompt injection.</strong> Recalled memories are fenced and size-capped as data, but a determined attacker can still write misleading tasks. Memories can be audited and deleted on the memory page.</li>
        </ul>
      </Panel>
    </div>
  )
}
