// Typed fetch wrappers for the FastAPI backend.

import { createSseParser } from '../lib/sse'
import type {
  AccountUsage,
  AdminUser,
  ApiKeyRecord,
  Plan,
  AttackInfo,
  Me,
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
  AgentBenchRun,
  BenchmarkResult,
  Certificate,
  Comparison,
  Improvement,
  ShareLink,
  SharedRun,
  Usage,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL || ''
const GROQ_KEY_STORAGE = 'agent_groq_key'

// Browsers sign in with an httpOnly session cookie the page can't read. Writes also carry
// this CSRF token, which only our own pages can learn (from /auth/me or the login reply).
let csrfToken: string | null = null

export function setCsrfToken(token: string | null | undefined): void {
  csrfToken = token ?? null
}

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

// The caller's own Groq key, if they chose to bring one. sessionStorage only: never sent to
// the server except as a header on each request, and gone when the tab closes.
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
  return err instanceof ApiError && err.status === 401
}

function authHeaders(method = 'GET'): Record<string, string> {
  const headers: Record<string, string> = {}
  const groqKey = getStoredGroqKey()
  if (groqKey) headers['X-Groq-Key'] = groqKey
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken
  return headers
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(options.method ?? 'GET'),
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

const del = <T>(endpoint: string) => request<T>(endpoint, { method: 'DELETE' })

// ── Accounts ──
export async function getMe(): Promise<Me> {
  const me = await request<Me>('/auth/me')
  setCsrfToken(me.csrf_token)
  return me
}
export async function login(email: string, password: string) {
  const res = await post<{ user: Me['user']; csrf_token: string }>('/auth/login', { email, password })
  setCsrfToken(res.csrf_token)
  return res
}
export async function verifyEmail(token: string) {
  const res = await post<{ user: Me['user']; csrf_token: string }>('/auth/verify', { token })
  setCsrfToken(res.csrf_token)
  return res
}
export async function logout() {
  const res = await post<{ logged_out: boolean }>('/auth/logout')
  setCsrfToken(null)
  return res
}
export const signup = (email: string, password: string) => post<{ message: string }>('/auth/signup', { email, password })
export const resendVerification = (email: string) => post<{ message: string }>('/auth/resend-verification', { email })
export const forgotPassword = (email: string) => post<{ message: string }>('/auth/forgot', { email })
export const resetPassword = (token: string, password: string) => post<{ message: string }>('/auth/reset', { token, password })
export async function changePassword(current_password: string, new_password: string) {
  const res = await post<{ changed: boolean; csrf_token: string }>('/account/password', { current_password, new_password })
  setCsrfToken(res.csrf_token)
  return res
}
export const startDemo = () => post<{ run_id: string; events_url: string; share_url: string }>('/demo/run')
export const deleteAccount = (password: string) =>
  request<{ deleted: boolean; runs: number; memories: number }>('/account', { method: 'DELETE', body: JSON.stringify({ password }) })

/** Fetch the account export and hand it to the browser as a file download. */
export async function downloadAccountExport(): Promise<void> {
  const data = await request<Record<string, unknown>>('/account/export')
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `code-agent-export-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Admin (operator and ADMIN_EMAILS accounts) ──
export const adminListUsers = (q = '') =>
  request<{ items: AdminUser[]; total: number }>(`/admin/users?${new URLSearchParams({ q, page_size: '100' })}`)
export const adminSetActive = (userId: string, active: boolean) =>
  post<{ active: boolean }>(`/admin/users/${encodeURIComponent(userId)}/active`, { active })
export const adminSetPlan = (userId: string, plan: string, days?: number) =>
  post<{ plan: string }>(`/admin/users/${encodeURIComponent(userId)}/plan`, days ? { plan, days } : { plan })
export const adminBackups = () => request<{ items: { name: string; bytes: number }[]; dir_configured: boolean }>('/admin/backups')
export const adminBackupNow = () => post<{ archive: string }>('/admin/backup')

export const getAccountUsage = () => request<AccountUsage>('/account/usage')
export const getPlans = () => request<{ items: Plan[]; payments_enabled: boolean }>('/plans')
export const listApiKeys = () => request<{ items: ApiKeyRecord[] }>('/account/keys')
export const createApiKey = (name: string) => post<{ key: string; record: ApiKeyRecord; message: string }>('/account/keys', { name })
export const revokeApiKey = (keyId: string) => del<{ revoked: string }>(`/account/keys/${encodeURIComponent(keyId)}`)

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
  options: { signal?: AbortSignal; lastEventId?: number; basePath?: string } = {},
): Promise<void> {
  const res = await fetch(`${BASE_URL}${options.basePath ?? '/runs'}/${encodeURIComponent(runId)}/events`, {
    credentials: 'same-origin',
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
export const getAgentBenchmarks = () => request<{ items: AgentBenchRun[] }>('/eval/agent')
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
