// Typed fetch wrappers for the FastAPI backend.

import { createSseParser } from '../lib/sse'
import type {
  AttackInfo,
  AttackResult,
  EvalResultOut,
  EvalRunOut,
  EvalRunRequest,
  EvalStatus,
  GenerateAndRepairRequest,
  HealthResponse,
  MemoryItem,
  MemoryPage,
  MemoryStats,
  PrResponse,
  RunAccepted,
  RunEvent,
  RunOut,
  RunPage,
  SandboxConfig,
  BenchmarkResult,
  Certificate,
  Comparison,
  Improvement,
  ShareLink,
  SharedRun,
  Usage,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL || ''
const API_KEY_STORAGE = 'agent_api_key'
const GROQ_KEY_STORAGE = 'agent_groq_key'

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// The key lives in sessionStorage only: never baked into the bundle, gone when the tab closes.
export function getStoredApiKey(): string | null {
  try {
    return sessionStorage.getItem(API_KEY_STORAGE)
  } catch {
    return null
  }
}

export function setStoredApiKey(key: string | null): void {
  try {
    if (key) sessionStorage.setItem(API_KEY_STORAGE, key)
    else sessionStorage.removeItem(API_KEY_STORAGE)
  } catch {
    // storage blocked (private mode); the key just won't persist
  }
}

// The caller's own Groq key, if they chose to bring one. Session-only, like the API key.
export function getStoredGroqKey(): string | null {
  try {
    return sessionStorage.getItem(GROQ_KEY_STORAGE)
  } catch {
    return null
  }
}

export function setStoredGroqKey(key: string | null): void {
  try {
    if (key) sessionStorage.setItem(GROQ_KEY_STORAGE, key)
    else sessionStorage.removeItem(GROQ_KEY_STORAGE)
  } catch {
    // storage blocked
  }
}

export function isAuthError(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 401 || err.status === 503)
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const apiKey = getStoredApiKey()
  const groqKey = getStoredGroqKey()
  if (apiKey) headers['X-API-Key'] = apiKey
  if (groqKey) headers['X-Groq-Key'] = groqKey
  return headers
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...((options.headers as Record<string, string>) || {}),
    },
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // body wasn't JSON
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`, detail)
  }
  return res.json()
}

const post = <T>(endpoint: string, body?: unknown) =>
  request<T>(endpoint, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

// ── System ──
export const getHealth = () => request<HealthResponse>('/health')
export const getSandboxConfig = () => request<SandboxConfig>('/sandbox/config')
export const listAttacks = () => request<{ items: AttackInfo[] }>('/sandbox/attacks')
export const runAttack = (name: string) => post<AttackResult>(`/sandbox/attacks/${encodeURIComponent(name)}`)

// ── Runs ──
export const startRun = (req: GenerateAndRepairRequest) => post<RunAccepted>('/runs', req)
export const getRun = (runId: string) => request<RunOut>(`/runs/${encodeURIComponent(runId)}`)

export function listRuns(params: { page?: number; pageSize?: number; q?: string; status?: string } = {}) {
  const search = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  })
  if (params.q) search.set('q', params.q)
  if (params.status && params.status !== 'all') search.set('status', params.status)
  return request<RunPage>(`/runs?${search}`)
}

export function openRunPr(runId: string): Promise<PrResponse> {
  return post<PrResponse>(`/runs/${encodeURIComponent(runId)}/pr`)
}

/**
 * Follow a run's server-sent events. Resolves when the stream ends (normally after
 * `run_finished`). Abort the signal to stop listening.
 */
export async function streamRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  options: { signal?: AbortSignal; lastEventId?: number } = {},
): Promise<void> {
  const res = await fetch(`${BASE_URL}/runs/${encodeURIComponent(runId)}/events`, {
    headers: {
      Accept: 'text/event-stream',
      ...authHeaders(),
      ...(options.lastEventId ? { 'Last-Event-ID': String(options.lastEventId) } : {}),
    },
    signal: options.signal,
  })
  if (!res.ok || !res.body) throw new ApiError(res.status, `Event stream failed (${res.status})`)

  const parser = createSseParser((msg) => {
    if (msg.id === null) return
    let payload: Record<string, unknown> = {}
    try {
      payload = msg.data ? JSON.parse(msg.data) : {}
    } catch {
      payload = {}
    }
    onEvent({ event_id: msg.id, type: msg.event, payload })
  })

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    parser.feed(value)
  }
}

// ── Memory ──
export function listMemory(params: { kind?: string; limit?: number } = {}) {
  const search = new URLSearchParams({ limit: String(params.limit ?? 100) })
  if (params.kind && params.kind !== 'all') search.set('kind', params.kind)
  return request<MemoryPage>(`/memory?${search}`)
}
export const getMemoryStats = () => request<MemoryStats>('/memory/stats')
export const searchMemory = (q: string, threshold = 0.3) =>
  request<{ items: MemoryItem[] }>(`/memory/search?${new URLSearchParams({ q, threshold: String(threshold) })}`)
export const deleteMemory = (id: string) => request<{ deleted: string }>(`/memory/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const pinMemory = (id: string, pinned: boolean) =>
  post<{ id: string; pinned: boolean }>(`/memory/${encodeURIComponent(id)}/pin?pinned=${pinned}`)

// ── Evaluation ──
export const getLatestEval = () => request<EvalResultOut>('/eval/latest')
export const getEvalHistory = () => request<{ items: BenchmarkResult[] }>('/eval/history')
export const getEvalStatus = (evalId: string) => request<EvalStatus>(`/eval/status/${encodeURIComponent(evalId)}`)
export const triggerEval = (req: EvalRunRequest) => post<EvalRunOut>('/eval/run', req)

// ── Compare, share, certificates, insight ──
export const startComparison = (req: GenerateAndRepairRequest & { models: string[] }) =>
  post<{ group_id: string; runs: { run_id: string; model: string }[] }>('/compare', req)
export const getComparison = (groupId: string) => request<Comparison>(`/compare/${encodeURIComponent(groupId)}`)
export const getCertificate = (runId: string) => request<Certificate>(`/runs/${encodeURIComponent(runId)}/certificate`)
export const shareRun = (runId: string) => post<ShareLink>(`/runs/${encodeURIComponent(runId)}/share`)
export const unshareRun = (runId: string) => request<{ shared: boolean }>(`/runs/${encodeURIComponent(runId)}/share`, { method: 'DELETE' })
export const getSharedRun = (token: string) => request<SharedRun>(`/shared/${encodeURIComponent(token)}`)
export const getUsage = () => request<Usage>('/usage')
export const getImprovement = (days = 60) => request<Improvement>(`/stats/improvement?days=${days}`)
