import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, verifyEmail } from '../../api/client'
import AuthLayout, { Notice } from '../../components/AuthLayout'

export default function Verify() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const token = params.get('token') ?? ''
  const [failure, setError] = useState<string | null>(null)
  const error = token ? failure : 'This link is missing its token.'
  const started = useRef(false)

  useEffect(() => {
    // Tokens are single-use: never send one twice (React's dev mode runs effects twice)
    if (started.current || !token) return
    started.current = true
    verifyEmail(token)
      .then(async () => {
        await qc.invalidateQueries()
        navigate('/?welcome=1', { replace: true })
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Something went wrong.'))
  }, [token, navigate, qc])

  return (
    <AuthLayout eyebrow="confirm email" title={error ? 'That link didn’t work' : 'Confirming…'}>
      {error ? (
        <div className="space-y-4">
          <Notice tone="danger">{error}</Notice>
          <Link to="/login" className="btn-secondary w-full justify-center">log in to get a new link</Link>
        </div>
      ) : (
        <Notice>Checking your link and signing you in.</Notice>
      )}
    </AuthLayout>
  )
}
