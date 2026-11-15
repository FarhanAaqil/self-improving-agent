import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, forgotPassword } from '../../api/client'
import AuthLayout, { Field, Notice } from '../../components/AuthLayout'

export default function Forgot() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      setSent((await forgotPassword(email)).message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    }
  }

  return (
    <AuthLayout eyebrow="reset password" title="Forgot your password?" footer={<Link className="underline" to="/login">Back to log in</Link>}>
      {sent ? (
        <Notice tone="success">{sent}</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Notice tone="danger">{error}</Notice>}
          <p className="text-sm text-ink-secondary">We’ll email you a link to choose a new one.</p>
          <Field label="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <button type="submit" className="btn-primary w-full justify-center">send reset link</button>
        </form>
      )}
    </AuthLayout>
  )
}
