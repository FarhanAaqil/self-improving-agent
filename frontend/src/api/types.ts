// TypeScript types mirroring app/schemas.py Pydantic models

export interface GenerateRequest {
  task_description: string
  model?: string | null
}

export interface ExecuteRequest {
  attempt_number?: number | null
  code_override?: string | null
}

export interface GenerateAndRepairRequest {
  task_description: string
  max_attempts?: number
  model?: string | null
  skip_agents?: string[]
}

export interface EvalRunRequest {
  benchmark?: string
  subset_size?: number | null
  skip_agents?: string[]
}

export interface GenerateOut {
  run_id: string
  code: string
  model: string
}

export interface ExecuteOut {
  run_id: string
  attempt_number: number
  success: boolean
  output?: string | null
  error?: string | null
  exit_code?: number | null
  latency_ms?: number | null
  sandboxed?: boolean
}

export interface AttemptOut {
  attempt_id?: number | null
  attempt_number: number
  generated_code: string
  stdout?: string | null
  stderr?: string | null
  exit_code?: number | null
  success: boolean
  latency_ms?: number | null
  tokens_used?: number | null
  model_name?: string | null
  critique_confidence?: number | null
  critique_reasoning?: string | null
  generated_tests?: string | null
  performance_notes?: string | null
  security_audit?: string | null
  quality_overall_score?: number | null
  quality_report_json?: string | null
  timestamp?: string | null
}

export interface RunOut {
  run_id: string
  task_description: string
  created_at?: string | null
  final_status: string
  total_attempts: number
  attempts: AttemptOut[]
}

export interface EvalResultOut {
  eval_id: string
  benchmark_name: string
  pass_at_1?: number | null
  pass_at_5?: number | null
  avg_attempts?: number | null
  avg_latency_ms?: number | null
  total_problems?: number | null
  run_at?: string | null
  raw?: Record<string, unknown> | null
}

export interface EvalRunOut {
  eval_id: string
  status: string
  message: string
}

export interface HealthResponse {
  status: string
  version: string
  docker_available: boolean
  demo_mode?: boolean
  github_configured?: boolean
}

export interface PrResponse {
  status: string
  pr_url?: string | null
  pr_number?: number | null
  branch?: string | null
  reason?: string | null
  error?: string | null
}
