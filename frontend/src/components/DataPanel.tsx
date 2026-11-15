import { useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, deleteAccount, downloadAccountExport } from '../api/client'
import { Panel } from './ui'

/** Export everything, or delete the account and everything in it. */
export default function DataPanel() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [exporting, setExporting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const exportAll = async () => {
    setExporting(true)
    setError(null)
    try {
      await downloadAccountExport()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The export failed. Try again.')
    } finally {
      setExporting(false)
    }
  }

  const remove = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await deleteAccount(password)
      qc.clear()
      navigate('/welcome?deleted=1', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That didn’t work. Try again.')
    }
  }

  return (
    <Panel title="your data">
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold text-ink">Export my runs</div>
            <div className="text-xs text-ink-secondary">One JSON file with every run, attempt and event, what the agent remembers, and your key names.</div>
          </div>
          <button type="button" className="btn-secondary shrink-0" onClick={exportAll} disabled={exporting}>
            <Download className="h-3.5 w-3.5" aria-hidden /> {exporting ? 'preparing…' : 'download'}
          </button>
        </div>

        <div className="border-t border-border pt-4">
          <div className="text-sm font-semibold text-status-danger">Delete my account</div>
          <div className="text-xs text-ink-secondary">
            Removes your runs, their attempts and events, everything the agent remembers for you, your API keys and sessions. This can’t be undone.
          </div>
          {!confirming ? (
            <button type="button" className="btn-secondary mt-3 text-status-danger" onClick={() => setConfirming(true)}>
              <Trash2 className="h-3.5 w-3.5" aria-hidden /> delete my account
            </button>
          ) : (
            <form onSubmit={remove} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="block flex-1">
                <span className="eyebrow">type your password to confirm</span>
                <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input mt-1" />
              </label>
              <button type="submit" className="btn-primary bg-status-danger">delete everything</button>
              <button type="button" className="btn-ghost" onClick={() => { setConfirming(false); setPassword('') }}>cancel</button>
            </form>
          )}
        </div>
        {error && <p role="alert" className="text-sm text-status-danger">{error}</p>}
      </div>
    </Panel>
  )
}
