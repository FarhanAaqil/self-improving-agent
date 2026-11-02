import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export type Motion = 'full' | 'reduced' | 'system'

export interface Preferences {
  theme: Theme
  motion: Motion
  defaultModel: string
  defaultAttempts: number
}

const KEY = 'agent_prefs'
const DEFAULTS: Preferences = { theme: 'system', motion: 'system', defaultModel: '', defaultAttempts: 3 }
const EVENT = 'agent-prefs-change'

function read(): Preferences {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS
  } catch {
    return DEFAULTS
  }
}

function prefersDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export function applyPreferences(prefs: Preferences = read()) {
  const root = document.documentElement
  const dark = prefs.theme === 'dark' || (prefs.theme === 'system' && prefersDark())
  root.dataset.theme = dark ? 'dark' : 'light'
  if (prefs.motion === 'reduced') root.dataset.motion = 'reduced'
  else delete root.dataset.motion
}

/** Per-viewer conveniences only; everything works if storage is unavailable. */
export function usePreferences() {
  const [prefs, setPrefs] = useState<Preferences>(read)

  useEffect(() => {
    applyPreferences(prefs)
  }, [prefs])

  useEffect(() => {
    const sync = () => setPrefs(read())
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    const onScheme = () => applyPreferences(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    media?.addEventListener?.('change', onScheme)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
      media?.removeEventListener?.('change', onScheme)
    }
  }, [])

  const update = useCallback((patch: Partial<Preferences>) => {
    const next = { ...read(), ...patch }
    try {
      localStorage.setItem(KEY, JSON.stringify(next))
    } catch {
      // storage blocked; keep the change for this session only
    }
    setPrefs(next)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  const isDark = prefs.theme === 'dark' || (prefs.theme === 'system' && prefersDark())
  return { prefs, update, isDark }
}
