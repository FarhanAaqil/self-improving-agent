import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, login } from '../../api/client'
import AuthLayout, { Field, Notice } from '../../components/AuthLayout'
import { safeNext } from '../../lib/redirect'

export default function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      await qc.invalidateQueries()
      navigate(safeNext(params.get('next')), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="log in"
      title="Welcome back"
      footer={<>New here? <Link className="font-semibold text-accent-ink underline" to="/signup">Create an account</Link></>}
    >
      <form onSubmit={submit} className="space-y-4">
        {params.get('reset') && <Notice tone="success">Password changed. Log in with the new one.</Notice>}
        {error && <Notice tone="danger">{error}</Notice>}
        <Field label="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field label="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit" className="btn-primary w-full justify-center" disabled={busy}>{busy ? 'logging in…' : 'log in'}</button>
        <Link to="/forgot" className="block text-center text-xs text-ink-secondary underline">Forgot your password?</Link>
      </form>
    </AuthLayout>
  )
}
