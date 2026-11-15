import { Brain, FlaskConical, ShieldCheck, Wrench } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import BrandLogo from '../components/BrandLogo'
import LiveDemo from '../components/LiveDemo'
import { useHealth } from '../hooks/useHealth'
import { useSession } from '../hooks/useSession'

const POINTS = [
  { icon: FlaskConical, title: 'Tests first', text: 'It writes spec tests from your description before any code, and only calls a run verified when every one passes.' },
  { icon: ShieldCheck, title: 'A locked sandbox', text: 'Code runs in a throwaway container with no network, no root, a read-only disk and hard limits. Never on your machine.' },
  { icon: Wrench, title: 'Fixes itself', text: 'When a test fails it reads the real traceback, works out the cause and tries again with that in hand.' },
  { icon: Brain, title: 'Remembers', text: 'Failures and the fixes that worked are kept in your private memory, so the next similar task starts smarter.' },
]

/** The public front door: what it is, a live run anyone can watch, and a way in. */
export default function Landing() {
  const { user } = useSession()
  const { data: health } = useHealth()
  if (user) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <BrandLogo variant="full" size="sm" />
          <nav className="flex items-center gap-1.5" aria-label="Site">
            <Link to="/pricing" className="btn-ghost px-2 py-1 text-xs">pricing</Link>
            <Link to="/login" className="btn-ghost px-2 py-1 text-xs">log in</Link>
            <Link to="/signup" className="btn-primary px-2.5 py-1 text-xs">sign up free</Link>
          </nav>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-5xl space-y-12 px-4 py-12">
        <section className="max-w-3xl">
          <div className="eyebrow">self-improving code agent</div>
          <h1 className="mt-2 font-mono text-3xl font-bold tracking-tight sm:text-4xl">Code that proves it works before you see it.</h1>
          <p className="mt-4 text-base text-ink-secondary">
            Describe a Python task. CODE_AGENT writes the tests, writes the code, runs both in a locked sandbox, repairs what breaks,
            and hands you the result with a certificate of what was checked.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/signup" className="btn-primary">start free</Link>
            <a href="#demo" className="btn-secondary">watch it work</a>
          </div>
          <p className="mt-3 text-xs text-ink-muted">Free runs on your own Groq key (free from Groq). No card needed.</p>
        </section>

        {health?.demo_enabled !== false && (
          <div id="demo">
            <LiveDemo />
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2" aria-label="How it works">
          {POINTS.map(({ icon: Icon, title, text }) => (
            <div key={title} className="panel p-5">
              <Icon className="h-5 w-5 text-accent" aria-hidden />
              <h2 className="mt-3 font-mono text-sm font-bold">{title}</h2>
              <p className="mt-1 text-sm text-ink-secondary">{text}</p>
            </div>
          ))}
        </section>

        <section className="panel flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-mono text-lg font-bold">Measured, not claimed</h2>
            <p className="text-sm text-ink-secondary">Benchmark results, the exact sandbox flags and real attack tests are all public.</p>
          </div>
          <div className="flex gap-2">
            <Link to="/eval" className="btn-secondary">benchmarks</Link>
            <Link to="/security" className="btn-secondary">security</Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-ink-muted">
          <span>CODE_AGENT</span>
          <nav className="flex flex-wrap gap-4" aria-label="Footer">
            <Link to="/pricing" className="hover:text-ink">pricing</Link>
            <Link to="/security" className="hover:text-ink">security</Link>
            <Link to="/eval" className="hover:text-ink">benchmarks</Link>
            <Link to="/terms" className="hover:text-ink">terms</Link>
            <Link to="/privacy" className="hover:text-ink">privacy</Link>
            <Link to="/acceptable-use" className="hover:text-ink">acceptable use</Link>
          </nav>
        </div>
      </footer>
    </div>
  )
}
