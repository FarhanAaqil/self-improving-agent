import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, resetPassword } from '../../api/client'
import AuthLayout, { Field, Notice } from '../../components/AuthLayout'

export default function Reset() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await resetPassword(params.get('token') ?? '', password)
      navigate('/login?reset=1', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    }
  }

  return (
    <AuthLayout eyebrow="reset password" title="Choose a new password">
      <form onSubmit={submit} className="space-y-4">
        {error && <Notice tone="danger">{error}</Notice>}
        <Field label="new password (10+ characters)" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit" className="btn-primary w-full justify-center">save password</button>
        <p className="text-xs text-ink-muted">Every other device signed in to this account will be signed out.</p>
      </form>
    </AuthLayout>
  )
}
