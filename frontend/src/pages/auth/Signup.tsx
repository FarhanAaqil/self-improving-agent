import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, resendVerification, signup } from '../../api/client'
import AuthLayout, { Field, Notice } from '../../components/AuthLayout'
import { useSession } from '../../hooks/useSession'

export default function Signup() {
  const { signupsOpen } = useSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setSent((await signup(email, password)).message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <AuthLayout eyebrow="check your inbox" title="One more step">
        <div className="space-y-4">
          <Notice tone="success">{sent}</Notice>
          <p className="text-sm text-ink-secondary">Open the link in the email to confirm <strong className="text-ink">{email}</strong>. It works once and expires in 48 hours.</p>
          <button type="button" className="btn-secondary w-full justify-center" onClick={() => resendVerification(email).then((r) => setSent(r.message))}>
            send it again
          </button>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      eyebrow="sign up"
      title="Create your account"
      footer={<>Already have one? <Link className="font-semibold text-accent-ink underline" to="/login">Log in</Link></>}
    >
      {!signupsOpen ? (
        <Notice>Sign-ups are closed on this server right now.</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Notice tone="danger">{error}</Notice>}
          <Field label="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Field label="password (10+ characters)" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit" className="btn-primary w-full justify-center" disabled={busy}>{busy ? 'creating…' : 'create account'}</button>
          <p className="text-xs text-ink-muted">You'll get an email to confirm your address before your first run.</p>
          <p className="text-xs text-ink-muted">
            By signing up you agree to the <Link to="/terms" className="underline">terms</Link>,{' '}
            <Link to="/privacy" className="underline">privacy policy</Link> and{' '}
            <Link to="/acceptable-use" className="underline">acceptable use policy</Link> (drafts).
          </p>
        </form>
      )}
    </AuthLayout>
  )
}
