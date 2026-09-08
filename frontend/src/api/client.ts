// Typed fetch wrappers for FastAPI backend endpoints

import type {
  EvalResultOut,
  EvalRunOut,
  EvalRunRequest,
  ExecuteOut,
  ExecuteRequest,
  GenerateAndRepairRequest,
  GenerateOut,
  GenerateRequest,
  HealthResponse,
  PrResponse,
  RunOut,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL || ''

class ApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`
  const apiKey =
    typeof window !== 'undefined'
      ? (localStorage.getItem('agent_api_key') || (import.meta.env.VITE_API_KEY as string | undefined))
      : undefined

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
    ...((options.headers as Record<string, string>) || {}),
  }

  const res = await fetch(url, { ...options, headers })

  if (!res.ok) {
    let errorDetail = res.statusText
    try {
      const data = await res.json()
      if (data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      // Body wasn't JSON; keep statusText
    }
    throw new ApiError(res.status, `API request failed (${res.status}): ${errorDetail}`, errorDetail)
  }

  return res.json()
}

// ── System ──

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

// ── Endpoint 1: POST /generate ──

export function generateCode(req: GenerateRequest): Promise<GenerateOut> {
  return request<GenerateOut>('/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ── Endpoint 2: POST /execute/{run_id} ──

export function executeRun(runId: string, req?: ExecuteRequest): Promise<ExecuteOut> {
  return request<ExecuteOut>(`/execute/${encodeURIComponent(runId)}`, {
    method: 'POST',
    body: req ? JSON.stringify(req) : undefined,
  })
}

// ── Endpoint 3: POST /generate-and-repair ──

export function generateAndRepair(req: GenerateAndRepairRequest): Promise<RunOut> {
  return request<RunOut>('/generate-and-repair', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ── Endpoint 4: GET /runs/{run_id} & GET /runs ──

export function getRun(runId: string): Promise<RunOut> {
  return request<RunOut>(`/runs/${encodeURIComponent(runId)}`)
}

export function listRuns(limit = 50): Promise<RunOut[]> {
  return request<RunOut[]>(`/runs?limit=${limit}`)
}

// ── Endpoint 5: GET /eval/latest ──

export function getLatestEval(): Promise<EvalResultOut> {
  return request<EvalResultOut>('/eval/latest')
}

// ── Endpoint 6: POST /eval/run ──

export function triggerEval(req: EvalRunRequest): Promise<EvalRunOut> {
  return request<EvalRunOut>('/eval/run', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ── PR Automation: POST /runs/{run_id}/pr ──

export function openRunPr(runId: string, repo?: string): Promise<PrResponse> {
  const query = repo ? `?repo=${encodeURIComponent(repo)}` : ''
  return request<PrResponse>(`/runs/${encodeURIComponent(runId)}/pr${query}`, {
    method: 'POST',
  })
}
