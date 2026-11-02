import { useQuery } from '@tanstack/react-query'
import { Fingerprint, ShieldCheck } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getSharedRun } from '../api/client'
import BrandLogo from '../components/BrandLogo'
import CodeBlock from '../components/CodeBlock'
import { Chip, EmptyState, Panel, Skeleton, StatusPill } from '../components/ui'
import VerifiedStamp from '../components/VerifiedStamp'
import { pct, relativeTime, score10 } from '../lib/format'

/** Public, read-only view of a run someone chose to share. No API key needed. */
export default function Shared() {
  const { token } = useParams<{ token: string }>()
  const { data: run, isLoading, error } = useQuery({
    queryKey: ['shared', token],
    queryFn: () => getSharedRun(token!),
    enabled: Boolean(token),
    retry: false,
  })

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-border bg-surface px-4 py-3">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <BrandLogo variant="full" size="sm" />
          <Chip tone="muted">shared, read-only</Chip>
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        {isLoading ? (
          <Skeleton className="h-96" />
        ) : error || !run ? (
          <EmptyState title="This link doesn't work anymore">It was never created, or its owner revoked it.</EmptyState>
        ) : (
          <>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <StatusPill status={run.final_status} />
                  <span className="font-mono text-[11px] text-ink-muted">{run.model_name} · {relativeTime(run.created_at)}</span>
                </div>
                <h1 className="mt-2 font-mono text-lg font-bold text-ink">{run.task_description}</h1>
              </div>
              {run.certificate && <VerifiedStamp status="verified" attempt={run.certificate.verified_on_attempt} />}
            </div>

            {run.certificate && (
              <Panel title="verification certificate" icon={<ShieldCheck className="h-3.5 w-3.5 text-status-success" aria-hidden />}>
                <dl className="grid grid-cols-2 gap-4 font-mono text-xs sm:grid-cols-4">
                  <div><dt className="text-ink-muted">spec tests</dt><dd className="text-ink">{run.certificate.tests.passed}/{run.certificate.tests.total}</dd></div>
                  <div><dt className="text-ink-muted">coverage</dt><dd className="text-ink">{pct(run.certificate.coverage)}</dd></div>
                  <div><dt className="text-ink-muted">quality</dt><dd className="text-ink">{score10(run.certificate.quality_score)} / 10</dd></div>
                  <div><dt className="text-ink-muted">attempts</dt><dd className="text-ink">{run.certificate.attempts}</dd></div>
                </dl>
                <p className="mt-4 flex items-start gap-2 break-all font-mono text-[11px] text-ink-muted">
                  <Fingerprint className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  sha256 {run.certificate.code_sha256}
                  {run.certificate.signed ? ' · signed by the server' : ' · unsigned'}
                </p>
              </Panel>
            )}

            <Panel title="code" bodyClassName="p-3">
              <CodeBlock code={run.final_code ?? run.attempts.find((a) => a.success)?.generated_code ?? run.attempts.at(-1)?.generated_code ?? ''} />
            </Panel>
            {run.spec_tests && (
              <Panel title="spec tests it had to pass" bodyClassName="p-3">
                <CodeBlock code={run.spec_tests} maxHeight="18rem" />
              </Panel>
            )}
            <p className="text-center text-sm text-ink-secondary">
              Made by a self-repairing agent that runs every line in a locked sandbox.{' '}
              <Link to="/" className="text-accent-ink underline">Try it</Link>
            </p>
          </>
        )}
      </main>
    </div>
  )
}
