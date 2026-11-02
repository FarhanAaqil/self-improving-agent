import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Brain,
  CheckCircle2,
  Download,
  FlaskConical,
  GitFork,
  GitPullRequest,
  Link2,
  Loader2,
  ScrollText,
  Terminal,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getCertificate, getRun, openRunPr, shareRun, unshareRun } from '../api/client'
import type { AttemptOut, Diagnosis, PrResponse, QualityReport, RunEvent, ShareLink, TestReport } from '../api/types'
import CodeBlock, { CopyButton } from '../components/CodeBlock'
import DiffView from '../components/DiffView'
import QualityRadar from '../components/QualityRadar'
import Stepper from '../components/Stepper'
import { Chip, EmptyState, ErrorNote, Meter, Panel, Skeleton, StatusPill } from '../components/ui'
import VerifiedStamp from '../components/VerifiedStamp'
import { useHealth } from '../hooks/useHealth'
import { useRunStream } from '../hooks/useRunStream'
import { compactNumber, duration, pct, relativeTime, score10 } from '../lib/format'
import { deriveStages, narrate, type Mood } from '../lib/narrate'

const MOOD_STYLE: Record<Mood, { dot: string; text: string }> = {
  thinking: { dot: 'bg-accent', text: 'text-ink' },
  memory: { dot: 'bg-cyan', text: 'text-cyan' },
  success: { dot: 'bg-status-success', text: 'text-status-success' },
  failure: { dot: 'bg-status-danger', text: 'text-ink' },
  neutral: { dot: 'bg-border-strong', text: 'text-ink-secondary' },
}

function parse<T>(json?: string | null): T | null {
  if (!json) return null
  try {
    return JSON.parse(json) as T
  } catch {
    return null
  }
}

/** Latest code per attempt as seen in the stream (before the run is saved in full). */
function liveAttempts(events: RunEvent[]) {
  const map = new Map<number, { code?: string; result?: Record<string, unknown> }>()
  for (const e of events) {
    const n = e.payload.attempt as number | undefined
    if (!n) continue
    const entry = map.get(n) ?? {}
    if (e.type === 'code_generated') entry.code = String(e.payload.code ?? '')
    if (e.type === 'sandbox_result') entry.result = e.payload
    map.set(n, entry)
  }
  return map
}

export default function RunTheater() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { data: health } = useHealth()
  const stream = useRunStream(runId)

  const { data: run, isLoading, error, refetch } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!),
    enabled: Boolean(runId),
  })

  // Pull the full saved record whenever an attempt lands and once the run ends
  const savedSignals = stream.events.filter((e) => ['sandbox_result', 'quality', 'run_finished'].includes(e.type)).length
  useEffect(() => {
    if (savedSignals) refetch()
  }, [savedSignals, refetch])

  const story = useMemo(() => stream.events.map(narrate).filter((s) => s !== null), [stream.events])
  const status = stream.finalStatus || run?.final_status
  const finished = stream.finished || ['success', 'failed', 'max_retries_exceeded', 'early_stopped'].includes(run?.final_status ?? '')
  const stages = useMemo(() => deriveStages(stream.events, finished ? status ?? undefined : undefined), [stream.events, finished, status])

  const live = useMemo(() => liveAttempts(stream.events), [stream.events])
  const attemptNumbers = useMemo(() => {
    const nums = new Set<number>([...(run?.attempts ?? []).map((a) => a.attempt_number), ...live.keys()])
    return [...nums].sort((a, b) => a - b)
  }, [run, live])

  const [selected, setSelected] = useState<number | null>(null)
  const current = selected ?? attemptNumbers[attemptNumbers.length - 1] ?? null
  const saved: AttemptOut | undefined = run?.attempts.find((a) => a.attempt_number === current)
  const code = saved?.generated_code ?? (current ? live.get(current)?.code : undefined)
  const previousCode = current && current > 1
    ? run?.attempts.find((a) => a.attempt_number === current - 1)?.generated_code ?? live.get(current - 1)?.code
    : undefined

  const [tab, setTab] = useState<'code' | 'diff' | 'tests' | 'final'>('code')
  const passing = run?.attempts.find((a) => a.success)
  const quality = parse<QualityReport>(passing?.quality_report_json)
  const report = parse<TestReport>(saved?.test_report_json) ?? (current ? (live.get(current)?.result as unknown as TestReport | undefined) ?? null : null)
  const diagnosis = parse<Diagnosis>(saved?.diagnosis_json)
  const sandboxed = saved?.sandboxed ?? (current ? (live.get(current)?.result?.sandboxed as boolean | undefined) : undefined)
  const stdout = saved?.stdout ?? (current ? String(live.get(current)?.result?.stdout ?? '') : '')
  const stderr = saved?.stderr ?? (current ? String(live.get(current)?.result?.stderr ?? '') : '')
  const working = !finished
  const runningSandbox = working && stream.events[stream.events.length - 1]?.type === 'sandbox_started'

  // Keep the story scrolled to the newest line while the run is live
  const storyEnd = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (working) storyEnd.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [story.length, working])

  const [pr, setPr] = useState<PrResponse | null>(null)
  const [prBusy, setPrBusy] = useState(false)
  const [share, setShare] = useState<ShareLink | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24" />
        <Skeleton className="h-96" />
      </div>
    )
  }
  if (error || !run) {
    return (
      <EmptyState title="I can't find that run" action={<Link to="/history" className="btn-secondary">back to the ledger</Link>}>
        {error instanceof Error ? error.message : `No run called ${runId}.`}
      </EmptyState>
    )
  }

  const finalCode = run.final_code ?? passing?.generated_code ?? code ?? ''
  const tokens = (run.prompt_tokens ?? 0) + (run.completion_tokens ?? 0)
  const saveFile = (content: string, name: string, type: string) => {
    const url = URL.createObjectURL(new Blob([content], { type }))
    const a = Object.assign(document.createElement('a'), { href: url, download: name })
    a.click()
    URL.revokeObjectURL(url)
  }
  const download = () => saveFile(finalCode, `${run.run_id}.py`, 'text/x-python')
  const downloadCertificate = async () => {
    try {
      const cert = await getCertificate(run.run_id)
      saveFile(JSON.stringify(cert, null, 2), `${run.run_id}.certificate.json`, 'application/json')
    } catch (e) {
      setShareError(e instanceof Error ? e.message : 'Could not export the certificate.')
    }
  }
  const toggleShare = async () => {
    setShareError(null)
    try {
      if (share) {
        await unshareRun(run.run_id)
        setShare(null)
      } else {
        setShare(await shareRun(run.run_id))
      }
    } catch (e) {
      setShareError(e instanceof Error ? e.message : 'Sharing failed.')
    }
  }
  const origin = typeof window !== 'undefined' ? window.location.origin : ''

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/history" className="inline-flex items-center gap-1.5 font-mono text-xs text-ink-secondary hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> ledger
        </Link>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-ink-muted">
          <span>{run.run_id}</span>
          <span aria-hidden>·</span>
          <span>{run.model_name}</span>
          <span aria-hidden>·</span>
          <span>{compactNumber(tokens)} tokens</span>
          <span aria-hidden>·</span>
          <span>{relativeTime(run.created_at)}</span>
        </div>
      </div>

      <header className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StatusPill status={status} />
            {stream.connected && working && <Chip tone="accent">live</Chip>}
          </div>
          <h1 className="mt-2 font-mono text-lg font-bold leading-snug text-ink sm:text-xl">{run.task_description}</h1>
        </div>
        {finished && status === 'success' && <VerifiedStamp status="verified" attempt={passing?.attempt_number} />}
        {finished && status !== 'success' && <VerifiedStamp status="stopped" />}
      </header>

      <Stepper stages={stages} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        {/* The agent's story */}
        <Panel title="what I'm doing" icon={<Loader2 className={`h-3.5 w-3.5 ${working ? 'animate-spin text-accent' : 'hidden'}`} aria-hidden />} bodyClassName="p-0">
          {run.memories.length > 0 && (
            <div className="border-b border-border bg-cyan-subtle px-4 py-3">
              <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold text-cyan">
                <Brain className="h-3.5 w-3.5" aria-hidden /> recalled from memory
              </div>
              <ul className="mt-1.5 space-y-1 text-xs text-ink-secondary">
                {run.memories.map((m, i) => (
                  <li key={m.id ?? i} className="line-clamp-2">
                    <span className="font-mono text-cyan">{Math.round(m.similarity * 100)}%</span>{' '}
                    {m.kind === 'fix' && m.lesson ? m.lesson : m.task}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ol className="max-h-[32rem] space-y-3 overflow-auto px-4 py-4" aria-live="polite" aria-relevant="additions">
            {story.length === 0 && (
              <li className="text-sm text-ink-muted">{finished ? 'This run finished before live events existed.' : 'Warming up…'}</li>
            )}
            {story.map((line) => (
              <li key={line.id} className="flex animate-rise-in gap-3">
                <span className={`mt-1.5 h-2 w-2 shrink-0 ${MOOD_STYLE[line.mood].dot}`} aria-hidden />
                <div className="min-w-0">
                  <p className={`text-sm ${MOOD_STYLE[line.mood].text}`}>{line.text}</p>
                  {line.detail && <p className="mt-0.5 break-words font-mono text-[11px] text-ink-muted">{line.detail}</p>}
                </div>
              </li>
            ))}
            <li ref={storyEnd} aria-hidden />
          </ol>
          {stream.error && working && <div className="border-t border-border px-4 py-2 font-mono text-[11px] text-status-warning">reconnecting…</div>}
        </Panel>

        {/* Code & sandbox */}
        <div className="min-w-0 space-y-4">
          {attemptNumbers.length > 0 && (
            <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Attempts">
              {attemptNumbers.map((n) => {
                const a = run.attempts.find((x) => x.attempt_number === n)
                const ok = a?.success ?? Boolean(live.get(n)?.result?.success)
                const done = Boolean(a || live.get(n)?.result)
                return (
                  <button
                    key={n}
                    type="button"
                    role="tab"
                    aria-selected={current === n}
                    onClick={() => setSelected(n)}
                    className={`chip px-2.5 py-1 ${current === n ? 'border-ink bg-surface text-ink' : 'border-border bg-surface-sunken text-ink-secondary'}`}
                  >
                    {!done ? <Loader2 className="h-3 w-3 animate-spin text-accent" aria-hidden /> : ok ? <CheckCircle2 className="h-3 w-3 text-status-success" aria-hidden /> : <XCircle className="h-3 w-3 text-status-danger" aria-hidden />}
                    attempt {n}
                  </button>
                )
              })}
            </div>
          )}

          <Panel
            bodyClassName="p-3"
            title={
              <span className="flex gap-1" role="tablist" aria-label="Views">
                {(['code', 'diff', 'tests', 'final'] as const)
                  .filter((t) => (t !== 'diff' || previousCode) && (t !== 'tests' || run.spec_tests) && (t !== 'final' || (finished && status === 'success')))
                  .map((t) => (
                    <button
                      key={t}
                      type="button"
                      role="tab"
                      aria-selected={tab === t}
                      onClick={() => setTab(t)}
                      className={`px-2 py-0.5 ${tab === t ? 'bg-ink text-ink-inverse' : 'text-ink-secondary hover:text-ink'}`}
                    >
                      {t === 'tests' ? 'spec tests' : t === 'final' ? 'final code' : t}
                    </button>
                  ))}
              </span>
            }
            actions={code ? <CopyButton text={tab === 'tests' ? run.spec_tests ?? '' : tab === 'final' ? finalCode : code} /> : null}
          >
            {tab === 'diff' && previousCode && code ? (
              <DiffView before={previousCode} after={code} beforeLabel={`attempt ${(current ?? 2) - 1}`} afterLabel={`attempt ${current}`} />
            ) : tab === 'tests' && run.spec_tests ? (
              <CodeBlock code={run.spec_tests} />
            ) : tab === 'final' ? (
              <CodeBlock code={finalCode} />
            ) : code ? (
              <CodeBlock code={code} streaming={working && !live.get(current ?? 0)?.result} />
            ) : (
              <div className="grid-paper flex h-48 items-center justify-center font-mono text-xs text-ink-muted">
                {working ? 'writing code…' : 'no code was produced'}
              </div>
            )}
          </Panel>

          <Panel title="sandbox" icon={<Terminal className="h-3.5 w-3.5" aria-hidden />} actions={sandboxed !== undefined && (
            <Chip tone={sandboxed ? 'success' : 'danger'}>{sandboxed ? 'docker · no network · nobody' : 'not sandboxed'}</Chip>
          )} bodyClassName="relative overflow-hidden p-0">
            {runningSandbox && <div className="pointer-events-none absolute inset-x-0 top-0 h-8 animate-scan bg-gradient-to-b from-transparent via-accent/15 to-transparent" aria-hidden />}
            {report && report.total > 0 && (
              <div className="border-b border-border px-4 py-3">
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="flex items-center gap-1.5 text-ink">
                    <FlaskConical className="h-3.5 w-3.5" aria-hidden />
                    {report.passed} / {report.total} tests passed
                  </span>
                  <span className="text-ink-muted">coverage {pct(report.coverage)}</span>
                </div>
                <div className="mt-2"><Meter value={report.total ? report.passed / report.total : 0} tone={report.passed === report.total ? 'success' : 'accent'} label="Tests passed" /></div>
                {report.failures?.length > 0 && (
                  <ul className="mt-3 space-y-1">
                    {report.failures.map((f) => (
                      <li key={f.test} className="flex gap-2 font-mono text-[11px]">
                        <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-status-danger" aria-hidden />
                        <span className="text-ink">{f.test}</span>
                        <span className="truncate text-ink-muted">{f.error}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <pre className="max-h-56 overflow-auto bg-surface-sunken px-4 py-3 font-mono text-[12px] leading-5" tabIndex={0}>
              {stdout && <span className="text-ink">{stdout}{'\n'}</span>}
              {stderr && <span className="text-status-danger">{stderr}</span>}
              {!stdout && !stderr && <span className="text-ink-muted">{runningSandbox ? '$ python - < solution.py' : 'no output'}</span>}
            </pre>
            {diagnosis && (
              <div className="border-t border-border bg-status-danger-subtle/50 px-4 py-3 text-sm">
                <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-status-danger">diagnosis</div>
                <p className="mt-1 text-ink">{diagnosis.summary}</p>
                {diagnosis.fix_plan && <p className="mt-1 text-xs text-ink-secondary">Plan: {diagnosis.fix_plan}</p>}
                <p className="mt-1 font-mono text-[11px] text-ink-muted">
                  blame: {diagnosis.blame} · retry confidence {Math.round(diagnosis.confidence * 100)}%
                </p>
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* Certificate */}
      {finished && status === 'success' && passing && (
        <section className="panel animate-rise-in shadow-ledger" aria-labelledby="cert-title">
          <div className="flex flex-col gap-1 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="eyebrow">verification certificate</div>
              <h2 id="cert-title" className="font-mono text-base font-bold text-ink">
                Passed {passing.tests_total ? `${passing.tests_passed}/${passing.tests_total} spec tests` : 'cleanly'} on attempt {passing.attempt_number}
              </h2>
            </div>
            <div className="font-mono text-3xl font-bold text-accent-ink">
              {score10(passing.quality_overall_score)}<span className="text-sm text-ink-muted"> / 10</span>
            </div>
          </div>
          <div className="grid gap-6 p-5 md:grid-cols-2">
            <div>{quality ? <QualityRadar report={quality} /> : <p className="text-sm text-ink-muted">No quality report for this run.</p>}</div>
            <div className="space-y-4">
              <dl className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div><dt className="text-ink-muted">attempts</dt><dd className="text-ink">{run.total_attempts}</dd></div>
                <div><dt className="text-ink-muted">sandbox time</dt><dd className="text-ink">{duration(run.attempts.reduce((s, a) => s + (a.latency_ms ?? 0), 0))}</dd></div>
                <div><dt className="text-ink-muted">coverage</dt><dd className="text-ink">{pct(passing.coverage)}</dd></div>
                <div><dt className="text-ink-muted">docstrings</dt><dd className="text-ink">{run.docs_applied ? 'added & re-verified' : 'not applied'}</dd></div>
                <div><dt className="text-ink-muted">bandit</dt><dd className="text-ink">{quality ? `${quality.bandit_issues.length} issue(s)` : '—'}</dd></div>
                <div><dt className="text-ink-muted">complexity</dt><dd className="text-ink">{quality?.cyclomatic_complexity ?? '—'}</dd></div>
              </dl>
              {quality && quality.bandit_issues.length > 0 && (
                <ul className="space-y-1 border-l-2 border-status-warning pl-3 text-xs text-ink-secondary">
                  {quality.bandit_issues.slice(0, 4).map((i) => (
                    <li key={`${i.test_id}-${i.line}`}><span className="font-mono">{i.severity} {i.test_id} L{i.line}</span>: {i.text}</li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={download} className="btn-primary"><Download className="h-3.5 w-3.5" aria-hidden /> download .py</button>
                <button type="button" onClick={() => navigate('/', { state: { task: run.task_description } })} className="btn-secondary">
                  <GitFork className="h-3.5 w-3.5" aria-hidden /> fork & edit
                </button>
                <button type="button" onClick={downloadCertificate} className="btn-secondary">
                  <ScrollText className="h-3.5 w-3.5" aria-hidden /> certificate
                </button>
                <button type="button" onClick={toggleShare} className="btn-secondary" aria-pressed={Boolean(share)}>
                  <Link2 className="h-3.5 w-3.5" aria-hidden /> {share ? 'stop sharing' : 'share link'}
                </button>
                {health?.github_configured && (
                  <button
                    type="button"
                    disabled={prBusy}
                    onClick={async () => {
                      setPrBusy(true)
                      try { setPr(await openRunPr(run.run_id)) } catch (e) { setPr({ status: 'error', error: e instanceof Error ? e.message : 'failed' }) } finally { setPrBusy(false) }
                    }}
                    className="btn-secondary"
                  >
                    <GitPullRequest className="h-3.5 w-3.5" aria-hidden /> {prBusy ? 'opening…' : 'open PR'}
                  </button>
                )}
              </div>
              {share && (
                <div className="space-y-2 border border-cyan/40 bg-cyan-subtle p-3 font-mono text-[11px]">
                  <div className="flex items-center justify-between gap-2">
                    <a href={share.url} target="_blank" rel="noreferrer" className="truncate text-cyan underline">{origin}{share.url}</a>
                    <CopyButton text={`${origin}${share.url}`} label="link" />
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <img src={share.badge} alt="verification badge" className="h-5" />
                    <CopyButton text={`[![verified](${origin}${share.badge})](${origin}${share.url})`} label="badge markdown" />
                  </div>
                </div>
              )}
              {shareError && <ErrorNote error={new Error(shareError)} />}
              {pr?.pr_url && <a href={pr.pr_url} target="_blank" rel="noreferrer" className="font-mono text-xs text-accent-ink underline">PR #{pr.pr_number} is open →</a>}
              {pr?.status === 'error' && <ErrorNote error={new Error(pr.error ?? 'Could not open the PR.')} />}
            </div>
          </div>
        </section>
      )}

      {finished && status !== 'success' && (
        <div className="panel flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-secondary">
            I couldn't get this one verified. What I learned is saved, so a rephrased or narrower task often works.
          </p>
          <button type="button" onClick={() => navigate('/', { state: { task: run.task_description } })} className="btn-primary shrink-0">
            <GitFork className="h-3.5 w-3.5" aria-hidden /> try again
          </button>
        </div>
      )}
    </div>
  )
}
