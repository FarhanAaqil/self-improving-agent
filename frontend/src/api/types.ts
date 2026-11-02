// TypeScript types mirroring app/schemas.py and the JSON the API returns.

export interface GenerateAndRepairRequest {
  task_description: string
  max_attempts?: number
  model?: string | null
  skip_agents?: string[]
}

export interface EvalRunRequest {
  benchmark?: 'humaneval'
  subset_size?: number
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
  model_name?: string | null
  critique_confidence?: number | null
  critique_reasoning?: string | null
  generated_tests?: string | null
  performance_notes?: string | null
  security_audit?: string | null
  quality_overall_score?: number | null
  quality_report_json?: string | null
  tests_passed?: number | null
  tests_total?: number | null
  coverage?: number | null
  test_report_json?: string | null
  diagnosis_json?: string | null
  sandboxed?: boolean | null
  timestamp?: string | null
}

export interface RecalledMemory {
  id?: string | null
  kind?: 'failure' | 'fix'
  task: string
  error?: string
  lesson?: string
  similarity: number
}

export interface RunOut {
  run_id: string
  task_description: string
  created_at?: string | null
  final_status: string
  total_attempts: number
  model_name?: string | null
  memories: RecalledMemory[]
  spec_tests?: string | null
  final_code?: string | null
  docs_applied?: boolean | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  finished_at?: string | null
  group_id?: string | null
  attempts: AttemptOut[]
}

export interface RunSummary {
  run_id: string
  task_description: string
  created_at?: string | null
  final_status: string
  total_attempts: number
  model_name?: string | null
  passed_on_attempt?: number | null
  quality_score?: number | null
  total_latency_ms?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  finished_at?: string | null
  group_id?: string | null
}

export interface RunPage {
  items: RunSummary[]
  total: number
  page: number
  page_size: number
  status_counts: Record<string, number>
}

export interface RunAccepted {
  run_id: string
  status: string
  events_url: string
}

export interface RunEvent {
  event_id: number
  type: string
  payload: Record<string, unknown>
}

export interface QualityReport {
  overall_score: number | null
  components: Record<'tests' | 'coverage' | 'security' | 'complexity' | 'performance', number | null>
  cyclomatic_complexity: number
  tests_passed?: number | null
  tests_total?: number | null
  estimated_coverage?: number | null
  bandit_issues: { severity: string; confidence: string; test_id: string; text: string; line: number }[]
  radon_blocks: { name: string; complexity: number; rank: string }[]
}

export interface Diagnosis {
  summary: string
  root_cause: string
  fix_plan: string
  blame: 'code' | 'tests'
  confidence: number
}

export interface TestReport {
  total: number
  passed: number
  coverage: number | null
  failures: { test: string; error: string }[]
  solution_error?: string | null
  tests_error?: string | null
}

export interface MemoryItem {
  id: string
  kind: 'failure' | 'fix'
  task: string
  code?: string
  error?: string
  signature?: string
  lesson?: string
  uses?: number
  pinned?: boolean
  timestamp?: string
  similarity?: number
}

export interface MemoryPage {
  total: number
  items: MemoryItem[]
}

export interface MemoryStats {
  total: number
  failures: number
  fixes: number
  times_recalled: number
}

export interface BenchmarkSide {
  pass_at_1: number
  passed: number
  ci95: [number, number]
  solve_at_k?: number
  k?: number
  avg_attempts?: number
}

export interface BenchmarkResult {
  eval_id: string
  benchmark: string
  suite: string
  model: string
  date: string
  run_at: string
  total_problems: number
  max_attempts: number
  sandboxed: boolean
  baseline: BenchmarkSide
  agent: BenchmarkSide & { solve_at_k: number; k: number; avg_attempts: number }
  repair_gain_pct: number
  avg_latency_ms: number
  tokens?: { prompt: number; completion: number }
  results?: {
    problem_id: string
    passed: boolean
    passed_at_attempt: number | null
    baseline_passed: boolean
    attempts_used: number
  }[]
}

export interface EvalResultOut {
  eval_id: string
  benchmark_name: string
  pass_at_1?: number | null
  pass_at_5?: number | null
  total_problems?: number | null
  run_at?: string | null
  raw?: Partial<BenchmarkResult> & { message?: string }
}

export interface EvalRunOut {
  eval_id: string
  status: string
  message: string
}

export interface EvalStatus {
  eval_id: string
  status: 'running' | 'done' | 'failed'
  done: number
  total: number
  recent: { id: string; passed: boolean }[]
  error?: string
}

export interface HealthResponse {
  status: string
  version: string
  docker_available: boolean
  demo_mode?: boolean
  github_configured?: boolean
  auth?: 'key' | 'open' | 'locked'
  code_override_enabled?: boolean
  memory_enabled?: boolean
  models?: string[]
  default_model?: string
}

export interface SandboxConfig {
  docker_available: boolean
  image: string
  timeout_seconds: number
  command: string[]
  host_fallback_enabled: boolean
}

export interface AttackInfo {
  name: string
  title: string
  description: string
}

export interface AttackResult {
  name: string
  blocked: boolean
  sandboxed: boolean
  verdict: string
  output: string | null
  error: string | null
  exit_code: number | null
  latency_ms: number
}

export interface PrResponse {
  status: string
  pr_url?: string | null
  pr_number?: number | null
  branch?: string | null
  reason?: string | null
  error?: string | null
}

// Statuses after which a run will never change again
export const TERMINAL_STATUSES = ['success', 'failed', 'max_retries_exceeded', 'early_stopped']

export function isTerminalStatus(status?: string | null): boolean {
  return Boolean(status && TERMINAL_STATUSES.includes(status))
}
