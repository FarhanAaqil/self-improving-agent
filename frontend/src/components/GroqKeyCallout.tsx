import { KeyRound } from 'lucide-react'
import { useState } from 'react'
import { setStoredGroqKey } from '../api/client'

/** Free accounts run on their own Groq key. Paste it once per browser tab, right here. */
export default function GroqKeyCallout({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState('')
  const looksRight = value.trim().startsWith('gsk_')

  return (
    <section className="border border-accent/40 bg-accent-subtle p-4" aria-labelledby="groq-key-title">
      <div className="flex items-center gap-2">
        <KeyRound className="h-4 w-4 text-accent-ink" aria-hidden />
        <h2 id="groq-key-title" className="font-mono text-sm font-bold text-accent-ink">Add your Groq key to start</h2>
      </div>
      <p className="mt-1.5 text-sm text-ink-secondary">
        Free accounts run on your own key, so your runs never wait on anyone else’s quota. Get one free at{' '}
        <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" className="font-semibold underline">console.groq.com</a>.
        It stays in this browser tab and is sent only with your runs; the server never stores it.
      </p>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault()
          if (!looksRight) return
          setStoredGroqKey(value.trim())
          onSaved()
        }}
      >
        <label className="flex-1">
          <span className="sr-only">Your Groq API key</span>
          <input type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} placeholder="gsk_…" className="input font-mono" />
        </label>
        <button type="submit" className="btn-primary" disabled={!looksRight}>use this key</button>
      </form>
    </section>
  )
}
