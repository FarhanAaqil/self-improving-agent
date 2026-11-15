import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import BrandLogo from './BrandLogo'

/** A quiet, centered frame for sign-up, login and the email-link pages. */
export default function AuthLayout({ eyebrow, title, children, footer }: { eyebrow: string; title: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-canvas px-4 py-10 text-ink">
      <Link to="/" className="mb-8" aria-label="CODE_AGENT home">
        <BrandLogo variant="full" size="md" />
      </Link>
      <main id="main" className="panel w-full max-w-sm p-6">
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="mt-1 font-mono text-xl font-bold tracking-tight">{title}</h1>
        <div className="mt-5">{children}</div>
      </main>
      {footer && <div className="mt-5 text-center text-sm text-ink-secondary">{footer}</div>}
    </div>
  )
}

export function Field({ label, ...input }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="eyebrow">{label}</span>
      <input {...input} className="input mt-1" />
    </label>
  )
}

export function Notice({ tone = 'muted', children }: { tone?: 'muted' | 'danger' | 'success'; children: ReactNode }) {
  const styles = {
    muted: 'border-border bg-surface-sunken text-ink-secondary',
    danger: 'border-status-danger/40 bg-status-danger-subtle text-status-danger',
    success: 'border-status-success/40 bg-status-success-subtle text-status-success',
  }
  return (
    <p role={tone === 'danger' ? 'alert' : 'status'} className={`border px-3 py-2 text-sm ${styles[tone]}`}>
      {children}
    </p>
  )
}
