import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Check } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getAccountUsage, getPlans } from '../api/client'
import type { Plan } from '../api/types'
import { PageHeader, Skeleton } from '../components/ui'
import { useSession } from '../hooks/useSession'
import { compactNumber } from '../lib/format'

function features(plan: Plan): string[] {
  return [
    plan.server_key
      ? `Runs on our Groq key: ${compactNumber(plan.server_token_budget)} tokens a day (or bring your own, uncapped)`
      : 'Runs on your own free Groq key',
    `${plan.runs_per_day} runs a day`,
    `${plan.concurrent_runs} run${plan.concurrent_runs === 1 ? '' : 's'} at a time`,
    `${plan.history_days} days of history`,
    'Docker sandbox, spec tests, repair loop and memory',
    'Signed certificates and share links',
  ]
}

export default function Pricing() {
  const { user } = useSession()
  const plans = useQuery({ queryKey: ['plans'], queryFn: getPlans })
  const usage = useQuery({ queryKey: ['account-usage'], queryFn: getAccountUsage, enabled: Boolean(user) })
  const current = user?.plan.name

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="pricing"
        title="Start free, upgrade when it earns it"
        lede="Every plan gets the same agent: tests written first, code run in a locked sandbox, repairs from real tracebacks, and memory of what went wrong."
      />
      {plans.isLoading ? (
        <Skeleton className="h-80" />
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {(plans.data?.items ?? []).map((plan) => {
            const isPro = plan.name !== 'free'
            return (
              <section key={plan.name} className={`panel flex flex-col p-6 ${isPro ? 'border-accent shadow-ledger' : ''}`} aria-labelledby={`plan-${plan.name}`}>
                <div className="flex items-baseline justify-between">
                  <h2 id={`plan-${plan.name}`} className="font-mono text-lg font-bold">{plan.label}</h2>
                  {current === plan.name && <span className="chip border-status-success/40 bg-status-success-subtle text-status-success">your plan</span>}
                </div>
                <div className="mt-2 font-mono text-3xl font-bold">{plan.price}</div>
                <ul className="mt-5 flex-1 space-y-2 text-sm">
                  {features(plan).map((f) => (
                    <li key={f} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-status-success" aria-hidden />{f}</li>
                  ))}
                </ul>
                <div className="mt-6">
                  {!user ? (
                    <Link to="/signup" className={`${isPro ? 'btn-primary' : 'btn-secondary'} w-full justify-center`}>start free</Link>
                  ) : isPro && current === 'free' ? (
                    usage.data?.upgrade_url ? (
                      <a href={usage.data.upgrade_url} target="_blank" rel="noreferrer" className="btn-primary w-full justify-center">
                        upgrade to Pro <ArrowUpRight className="h-3 w-3" aria-hidden />
                      </a>
                    ) : (
                      <p className="text-center text-xs text-ink-muted">Upgrades aren’t open on this server yet.</p>
                    )
                  ) : null}
                </div>
              </section>
            )
          })}
        </div>
      )}
      <p className="text-xs text-ink-muted">
        After paying, your account is upgraded and stays Pro until the paid period ends; then it’s Free again, with your runs and keys intact
        (history older than the Free limit is removed).
      </p>
    </div>
  )
}
