import { KeyRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getStoredApiKey, setStoredApiKey } from '../api/client'

export default function ApiKeyDialog({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [value, setValue] = useState('')

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) {
      setValue(getStoredApiKey() ?? '')
      el.showModal()
    } else if (!open && el.open) {
      el.close()
    }
  }, [open])

  const save = (key: string | null) => {
    setStoredApiKey(key)
    onSaved()
    onClose()
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      className="w-[min(92vw,440px)] border border-border-strong bg-surface p-0 text-ink shadow-ledger backdrop:bg-ink/40"
    >
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault()
          save(value.trim() || null)
        }}
        className="space-y-4 p-5"
      >
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-accent" aria-hidden />
          <h2 className="font-mono text-sm font-bold">API key</h2>
        </div>
        <p className="text-sm text-ink-secondary">
          This server asks for a key. It stays in this browser tab only and is sent as an
          <code className="mx-1 bg-surface-sunken px-1 font-mono text-xs">X-API-Key</code>header.
        </p>
        <label className="block">
          <span className="eyebrow">key</span>
          <input
            autoFocus
            type="password"
            autoComplete="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="input mt-1 font-mono"
            placeholder="paste your API key"
          />
        </label>
        <div className="flex justify-between gap-2">
          <button type="button" className="btn-ghost" onClick={() => save(null)}>
            forget key
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>
              cancel
            </button>
            <button type="submit" className="btn-primary">
              save
            </button>
          </div>
        </div>
      </form>
    </dialog>
  )
}
