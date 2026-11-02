<p align="center">
  <img src="assets/brand-banner.jpg" alt="CODE_AGENT: Verification Ledger Banner" width="100%" />
</p>

# 🧠 CODE_AGENT — Self-Improving Code Agent & Verification Ledger

> A sandboxed, self-repairing autonomous coding system that executes untrusted Python in isolated Docker containers, critiques failure tracebacks to repair bugs, learns negative patterns via ChromaDB vector memory, and audits code quality through multi-agent review.

[![CI](https://github.com/FarhanAaqil/self-improving-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/FarhanAaqil/self-improving-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20TS-61DAFB?style=flat&logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Sandbox-Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Qwen3%20%2F%20gpt--oss-F55036?style=flat)
![ChromaDB](https://img.shields.io/badge/Memory-ChromaDB-orange?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 📸 Product Tour & Demos

Explore the core workflows and interfaces of the CODE_AGENT verification ledger.

### 1. Task Synthesis & Live Viewfinder (`/`)
Interactive developer workspace where users submit task specifications with prompt quick-picks, model selection (served live from `/models`), and an active pipeline viewfinder.

<p align="center">
  <img src="assets/screenshots/01-new-run.png" alt="New Run Workspace" width="100%" />
</p>

---

### 2. Autonomous Multi-Attempt Execution & Live Stepper
Watch the multi-agent critique loop synthesize code, mount it into an ephemeral cgroup container, capture tracebacks upon failure, and automatically repair errors in real time.

<p align="center">
  <img src="assets/screenshots/02-live-execution.png" alt="Live Execution Stepper" width="100%" />
</p>

---

### 3. Audit Ledger & Historical Runs (`/history`)
Comprehensive audit ledger of all generated programs with status filter pills, search bar, execution pass/fail metrics, quality ratings (out of 10), attempt counters, and pagination.

<p align="center">
  <img src="assets/screenshots/03-run-history.png" alt="Audit Ledger and Run History" width="100%" />
</p>

---

### 4. Deep Run Inspection, Quality Audit & Diff View (`/runs/{run_id}`)
Examine individual attempts with stdout/stderr traces, AST security audit results, algorithmic complexity profiling, unified code diffs, one-click code download, and automated GitHub Pull Request creation.

<p align="center">
  <img src="assets/screenshots/04-run-detail.png" alt="Deep Run Inspection" width="100%" />
</p>

---

### 5. HumanEval Benchmark Dashboard (`/eval`)
Benchmark telemetry comparing a single-shot baseline with the repairing agent on official HumanEval, with confidence intervals.

<p align="center">
  <img src="assets/screenshots/05-eval-dashboard.png" alt="Evaluation Dashboard" width="100%" />
</p>

---

### 6. Security Architecture & Threat Model (`/security`)
Official cryptographic sandbox specification detailing kernel cgroups, network disconnection (`--network none`), read-only root filesystems, and static AST security audits.

<p align="center">
  <img src="assets/screenshots/06-security-threat-model.png" alt="Security Architecture and Threat Model" width="100%" />
</p>

---

## 1. Problem Statement

Most AI code generators are single-shot and unvalidated: they emit code and hope for the best, with zero execution feedback. When developers run generated code locally, they face two major problems: hallucinated bugs that require tedious manual troubleshooting, and severe security hazards when executing untrusted AI output directly on the host machine. 

The **Self-Improving Code Agent** closes this loop:
1. **Quarantined Execution:** It executes untrusted model code inside an isolated, unprivileged Docker sandbox with zero network access and strict memory caps.
2. **Iterative Critique & Repair:** When runtime exceptions occur, structured tracebacks are captured and passed back to an LLM critique agent to fix the code automatically.
3. **Persistent Negative Memory:** When runs terminally fail, the failure pattern and traceback signature are indexed into ChromaDB vector memory, preventing identical mistakes in future tasks.
4. **Autonomous Quality Gates:** Passing code is subjected to multi-agent critique — static AST security review, Big-O algorithmic profiling, unit test synthesis, and docstring formatting.

---

## 2. Security Model (First & Foremost)

Executing untrusted, model-generated code on the host filesystem is dangerous. In this project, **all code execution is strictly quarantined within an ephemeral Docker container** configured with Defense-in-Depth restrictions:

| Guardrail | Docker Configuration | Threat Mitigated |
|---|---|---|
| **Network Quarantined** | `--network none` | Prevents data exfiltration, reverse shells, and malicious outbound requests |
| **Filesystem Lockdown** | `--read-only` | Prevents overwriting host mount points, mutating binaries, or persistent backdoors |
| **Ephemeral Scratch** | `--tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m` | Provides temporary scratch space only; execution inside `/tmp` is disabled |
| **Memory Throttle** | `--memory=256m --memory-swap=256m` | Blocks memory exhaustion attacks and OOM crashes of the host kernel |
| **CPU Throttle** | `--cpus=0.5` | Prevents CPU-spinning cryptominers and unbounded infinite loops |
| **Process Limit** | `--pids-limit 64` | Stops fork bombs before they reach the host |
| **No Privileges** | `--user 65534:65534 --cap-drop ALL --security-opt no-new-privileges` | Runs as `nobody`, with no Linux capabilities and no way to regain them |
| **No Host Paths** | code piped over stdin (`python -`) | Nothing from the host filesystem is mounted into the container |
| **Host-Side Termination**| `subprocess.run(..., timeout=10)` + `docker kill` | Host daemon forcefully terminates hanging processes regardless of in-script signal masks |

If Docker is not available the API **refuses to execute** instead of falling back to the host. API access is **fail-closed**: outside `APP_ENV=development`, every endpoint except `/health` requires `API_KEY`.

### Adversarial Test Suite
The security perimeter is guarded by 8 real attacks in `tests/fixtures/adversarial/`, executed in CI against a live Docker daemon. A test passes only when the attack is visibly stopped:
1. **Outbound Network:** HTTP request to the internet — blocked (`--network none`).
2. **Host Secrets:** Looks for the Docker socket, server API keys and host home directories — nothing visible.
3. **Fork Bomb:** A real `os.fork()` loop — stopped by `--pids-limit`.
4. **Memory Exhaustion:** Allocates 1GB — capped by `--memory`.
5. **Filesystem Tampering:** Writes outside `/tmp` — blocked (read-only root).
6. **`/tmp` Execution:** Drops and runs a script in `/tmp` — blocked (`noexec`).
7. **Privilege Escalation:** Checks for root and tries `setuid(0)` — refused.
8. **Outlive Host Parent:** Spawns a child and hangs — killed by the host-side timeout.

---

## 3. Architecture

```mermaid
graph TD
    A[Task] --> B[POST /runs → background job]
    B --> C[Recall memory<br/>failures + lessons, cosine ≥ 0.75]
    C --> D[Test agent writes spec tests<br/>from the task, before any code]
    D --> E[Generator writes code<br/>to satisfy the spec tests]
    E --> F[Verification harness in Docker<br/>runs code + tests, traces coverage]
    F -->|tests fail| G[Diagnose: root cause, fix plan,<br/>blame code or tests, retry confidence]
    G -->|confidence < 0.3| H[Early stop + remember failure]
    G -->|tests at fault, once| D
    G -->|repair| E
    F -->|all tests pass| I[Review: performance, LLM security audit,<br/>bandit, radon, critique]
    I --> J[Documentation agent<br/>kept only if it still passes]
    J --> K[Quality score from measured data]
    K --> L[Remember the lesson that fixed it]
    B -.every step.-> M[(run_events)] -.SSE.-> N[Live UI]
```

**What counts as success:** every spec test passes inside the sandbox. A clean exit code is not enough. The repair prompt contains the previous code, the failing tests and the diagnosis, so the model fixes what it can actually see.

---

## 4. Evaluation & Benchmark Results

`python -m eval.benchmark` runs the **official HumanEval** problems (all 164 are vendored in `eval/data/`, MIT licensed) with their original `check()` tests, inside the Docker sandbox.

- **Baseline:** one single-shot completion per problem, no feedback.
- **Agent pass@1:** the agent's first attempt (an independent sample).
- **Agent solve@k:** solved within k attempts with repair.
- **No test leakage:** after a failure the agent only learns the exception type, never the assertion source or expected values.
- **Honest error bars:** 95% Wilson confidence intervals. Results that did not run in the sandbox are refused.

<!-- BENCHMARK_TABLE_START -->
Official HumanEval, 40 problems, `qwen/qwen3.8-27b`, run 2026-11-02 in the Docker sandbox. Brackets show the 95% confidence interval.

| Metric | Result |
|---|---|
| Baseline pass@1 (single shot, no feedback) | 100.0% [91.2–100.0] |
| Agent pass@1 (first attempt) | 97.5% |
| Agent solve@3 (with repair) | 100.0% [91.2–100.0] |
| Gain from repair | +0.0 pts |
| Average attempts | 1.02 |
<!-- BENCHMARK_TABLE_END -->

> **Reading this honestly:** modern models have largely saturated HumanEval, so the baseline sits at the ceiling and repair has nothing left to add here. The repair loop is aimed at harder, under-specified tasks, and a tougher suite such as HumanEval+ or MBPP+ is the next benchmark to add.

*The table is generated from committed JSON in `results/` by `scripts/generate_readme_table.py`; it is never hand-typed. Older numbers from the simplified 50-problem set are archived in `results/legacy/` with an explanation of why they are not comparable.*

---

## 5. Vector Memory (ChromaDB)

`app/memory.py` keeps two kinds of memories, embedded with Chroma's bundled ONNX MiniLM model (no torch needed):
- **Failures:** tasks that never passed, with the code that was tried and its error signature.
- **Lessons:** tasks that failed first and then passed, with the error and the fix that worked.
- **Recall:** before a run starts, similar memories above a 0.75 cosine threshold are recalled, shown in the UI, and given to the generator.
- **Treated as data:** memories come from user input, so they are passed as fenced, size-capped reference data in a user message, never as system instructions.
- **Manageable:** browse, search, pin and delete memories through `/memory`.

---

## 6. Setup & Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend development)
- Docker Desktop or Docker Engine active
- Free Groq API Key from [console.groq.com](https://console.groq.com)

### Option A: Docker Compose (Fastest)

```bash
# Clone the repository
git clone https://github.com/FarhanAaqil/self-improving-agent.git
cd self-improving-agent

# Copy the example env and add your Groq API key
cp .env.example .env

# Build and run the entire stack
docker compose up --build
```
Navigate to `http://localhost:8000` to interact with the full React application.

### Option B: Local Development

```bash
# 1. Install Python dependencies in editable mode and create your .env
pip install -e ".[dev]"
cp .env.example .env   # APP_ENV=development keeps the API open locally

# 2. Build the React frontend SPA
cd frontend
npm install
npm run build
cd ..

# 3. Pull the execution sandbox container
docker pull python:3.11-slim

# 4. Start the FastAPI backend
uvicorn app.main:app --reload --port 8000
```

---

## 7. API Reference

Interactive OpenAPI documentation and Swagger UI are hosted at `http://localhost:8000/docs`.

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Health telemetry, Docker engine availability, and demo mode flags |
| `POST` | `/generate` | Generate initial code without execution |
| `POST` | `/execute/{run_id}` | Dispatch a specific run's code into the Docker sandbox |
| `POST` | `/generate-and-repair` | Full loop, synchronous (blocks until done) |
| `POST` | `/runs` | Full loop in the background; returns `run_id` immediately (202) |
| `GET` | `/runs/{run_id}/events` | Server-sent events: every step of a run, live, resumable with `Last-Event-ID` |
| `GET` | `/runs` | Paginated run summaries (`page`, `page_size`, `q`, `status`) |
| `GET` | `/runs/{run_id}` | Full attempt history, spec tests, diagnosis, recalled memories, quality report |
| `GET` | `/memory`, `/memory/search`, `/memory/stats` | Browse and search what the agent has learned |
| `DELETE` | `/memory/{id}` | Forget a memory (`POST /memory/{id}/pin` to pin one) |
| `GET` | `/models`, `/sandbox/config` | Available models and the exact sandbox command in use |
| `POST` | `/runs/{run_id}/pr` | Automated GitHub Pull Request opening with verified solution |
| `GET` | `/eval/latest`, `/eval/history` | Latest and past benchmark results |
| `POST` | `/eval/run` | Start a benchmark run (`GET /eval/status/{id}` for progress) |

---

## 8. Honest Limitations & Threat Model Boundary

- **Python-Only Scope:** The current iteration evaluates and repairs Python code exclusively. Multi-language polyglot support is omitted by design to ensure tight sandbox isolation and deterministic AST metrics.
- **Docker-Socket Privilege Tradeoff:** The backend service container mounts `/var/run/docker.sock` to dynamically spawn sibling sandbox containers. Mounting the host Docker socket provides root-equivalent access to the host daemon. In production deployments, this should be replaced with rootless container engines, gVisor (`runsc`), Kata Containers, or cloud microVM executors (E2B / Modal).
- **Free-Tier LLM Rate Limits:** Benchmarks are tuned for Groq's free-tier rate limits. Evaluating the entire 164-problem HumanEval set in rapid succession may trigger token bucket throttling.
- **No Infinite Self-Modification:** The agent modifies its generated solutions in memory; it does not overwrite its own core source code.

---

## 9. Deliverables Verification (PRD Section 10)

- [x] **Hardened Docker Sandbox:** Full isolation flags (`--network none`, `--read-only`, `--tmpfs`, `--memory=256m`) verified in `app/sandbox.py`.
- [x] **5 Adversarial Tests:** Passing in CI under `tests/test_sandbox_isolation.py`.
- [x] **SQLite Persistence:** Clean schema migrations and attempt tracking in `app/db.py`.
- [x] **FastAPI Service:** 6 endpoints + Swagger docs live at `/docs`.
- [x] **React SPA:** Vite + TS + TailwindCSS dashboard with live attempt polling and code diffs.
- [x] **Post-Success Review Agents:** Test, Performance, Security Audit, and Documentation agents in `app/`.
- [x] **Vector Memory:** ChromaDB failure storage and prompt injection with 0.75 similarity gate in `app/memory.py`.
- [x] **50-Problem HumanEval Evaluation:** Committed real results in `results/humaneval_2026-09-12.json`.
- [x] **15 Custom YAML Tasks:** Hand-written realistic engineering specs with custom runner in `eval/`.
- [x] **Automated Table Generation:** `scripts/generate_readme_table.py` generates README benchmark metrics.
- [x] **Full CI Pipeline:** GitHub Actions running lint, unit tests, regression-gated smoke eval, and integration tests.
- [x] **GitHub PR Automation:** Gated PR generation agent in `app/github_agent.py`.
- [x] **Demo Deployment Config:** `render.yaml` configured with demo badge mode.

---

## Author

**Farhan Aaqil** — B.Tech AI/ML  
[![GitHub](https://img.shields.io/badge/GitHub-FarhanAaqil-181717?style=flat&logo=github)](https://github.com/FarhanAaqil)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-farhan--aaqil-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/farhan-aaqil-4730432bb)
