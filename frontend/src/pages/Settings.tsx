import { Monitor, Moon, Sun } from 'lucide-react'
import { useState } from 'react'
import { getStoredGroqKey, setStoredGroqKey } from '../api/client'
import { ApiKeysPanel, ProfilePanel } from '../components/AccountPanels'
import { PageHeader, Panel } from '../components/ui'
import { useHealth } from '../hooks/useHealth'
import { usePreferences, type Motion, type Theme } from '../hooks/usePreferences'
import { useSession } from '../hooks/useSession'

function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T
  options: { id: T; label: string; icon?: React.ReactNode }[]
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex border border-border">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          onClick={() => onChange(o.id)}
          className={`flex items-center gap-1.5 px-3 py-1.5 font-mono text-xs ${value === o.id ? 'bg-ink text-ink-inverse' : 'bg-surface text-ink-secondary hover:text-ink'}`}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function Settings() {
  const { prefs, update } = usePreferences()
  const { data: health } = useHealth()
  const { user } = useSession()
  const [groqKey, setGroqKey] = useState(() => getStoredGroqKey() ?? '')
  const [groqSaved, setGroqSaved] = useState(false)

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="settings" title="Make it yours" lede="Your account, keys and preferences. Appearance and run defaults live in this browser only." />

      {user && <ProfilePanel user={user} />}
      {user && <ApiKeysPanel />}

      <Panel title="appearance">
        <div className="space-y-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-ink">Theme</div>
              <div className="text-xs text-ink-secondary">Light ledger by day, night shift by night.</div>
            </div>
            <Segmented<Theme>
              label="Theme"
              value={prefs.theme}
              onChange={(theme) => update({ theme })}
              options={[
                { id: 'light', label: 'light', icon: <Sun className="h-3 w-3" aria-hidden /> },
                { id: 'dark', label: 'night', icon: <Moon className="h-3 w-3" aria-hidden /> },
                { id: 'system', label: 'system', icon: <Monitor className="h-3 w-3" aria-hidden /> },
              ]}
            />
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-ink">Motion</div>
              <div className="text-xs text-ink-secondary">Stamps, pulses and scan lines. Reduced keeps everything still.</div>
            </div>
            <Segmented<Motion>
              label="Motion"
              value={prefs.motion}
              onChange={(motion) => update({ motion })}
              options={[
                { id: 'full', label: 'full' },
                { id: 'reduced', label: 'reduced' },
                { id: 'system', label: 'system' },
              ]}
            />
          </div>
        </div>
      </Panel>

      <Panel title="runs">
        <div className="grid gap-5 md:grid-cols-2">
          <label className="block">
            <span className="eyebrow">default model</span>
            <select value={prefs.defaultModel} onChange={(e) => update({ defaultModel: e.target.value })} className="input mt-1 font-mono">
              <option value="">server default ({health?.default_model ?? '…'})</option>
              {(health?.models ?? []).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="eyebrow">default attempts: <span className="text-accent-ink">{prefs.defaultAttempts}</span></span>
            <input type="range" min={1} max={10} value={prefs.defaultAttempts} onChange={(e) => update({ defaultAttempts: Number(e.target.value) })} className="mt-3 w-full accent-[rgb(var(--accent))]" />
          </label>
        </div>
      </Panel>

      {!user && health?.auth === 'open' && (
        <Panel title="access">
          <p className="text-sm text-ink-secondary">This server is in local development mode, so it works without an account. Sign up to try accounts and API keys.</p>
        </Panel>
      )}

      {health?.byo_groq_key && (
        <Panel title="your own groq key">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              setStoredGroqKey(groqKey.trim() || null)
              setGroqSaved(true)
              setTimeout(() => setGroqSaved(false), 1500)
            }}
          >
            <p className="text-sm text-ink-secondary">
              Runs started from this tab will use your key instead of the server's. It is sent with each request,
              used only for that run, and never stored on the server.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="flex-1">
                <span className="sr-only">Groq API key</span>
                <input type="password" autoComplete="off" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder="gsk_…" className="input font-mono" />
              </label>
              <button type="submit" className="btn-secondary">{groqSaved ? 'saved' : groqKey ? 'save' : 'clear'}</button>
            </div>
          </form>
        </Panel>
      )}
    </div>
  )
}
