# 🧠 Self-Improving Code Agent

> An AI agent that writes Python code, executes it in a sandbox, critiques its own output, learns from failures via vector memory, and benchmarks improvement — built on a fully zero-cost stack.

[![CI](https://github.com/FarhanAaqil/self-improving-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/FarhanAaqil/self-improving-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React%20%2B%20TS-61DAFB?style=flat&logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Sandbox-Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama%203.3%2070B-F55036?style=flat)
![ChromaDB](https://img.shields.io/badge/Memory-ChromaDB-orange?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## What It Does

Most code agents generate once and stop. This one keeps going — it critiques its own solution, stores failures in vector memory so it doesn't repeat them, and benchmarks whether the revised code is actually faster and leaner than the original.

**Example tasks:**
```
Implement a binary search tree with insert and traversal
Write a function to find all prime numbers up to N using the Sieve of Eratosthenes
Solve the two-sum problem with O(n) time complexity
Build a LRU cache with O(1) get and put
```

---

## Architecture

```
User Task
     │
     ▼
┌──────────────────────┐
│   Memory Lookup      │  ChromaDB retrieves similar past failures
│   (sentence-trans.)  │  and injects them as "what not to do" context
└──────────┬───────────┘
           │
     ▼
┌──────────────────────┐
│   Generator Agent    │  Llama 3.3 70B writes Python code
│   + Sandbox Loop     │  subprocess.run() executes; errors loop back
│                      │  up to N retries with traceback appended
└──────────┬───────────┘
           │ working code
     ▼
┌──────────────────────┐
│   Critique Agent     │  Second independent LLM pass reviews for
│                      │  efficiency, edge cases, and redundancy
│                      │  Suggests a concrete improved version
└──────────┬───────────┘
           │ approved / improved code
     ▼
┌──────────────────────┐
│   Benchmark          │  timeit measures runtime (ms)
│                      │  tracemalloc measures peak memory (KB)
│                      │  before-critique vs after-critique delta shown
└──────────┬───────────┘
           │
     ▼
┌──────────────────────┐
│   Memory Write       │  Failures + fixes stored in ChromaDB
│                      │  so the next similar task starts smarter
└──────────────────────┘
```

---

## Vector Memory (ChromaDB)

The agent integrates a persistent vector memory layer using local ChromaDB and `all-MiniLM-L6-v2` embeddings:
- **Failure Storage:** When an attempt terminally fails (`max_retries_exceeded` or `early_stopped`), the task specification, failed code, and execution traceback are stored in the local ChromaDB `failures` collection.
- **Prompt Injection:** On attempt 1 of future tasks, vector memory is queried for semantically similar historical failures.
- **0.75 Similarity Threshold:** Only failure memories with cosine similarity **>= 0.75** are injected into the generator prompt under `"PAST FAILURES TO AVOID"` few-shot context. Thresholds below 0.75 risk introducing unrelated code as negative examples.

---

## Zero-Cost Stack

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq API — Llama 3.3 70B | Free tier |
| Code execution | Python `subprocess` | Free |
| Vector memory | ChromaDB (local) | Free |
| Embeddings | sentence-transformers (local) | Free |
| Benchmarking | `timeit` + `tracemalloc` (stdlib) | Free |
| UI | Streamlit | Free |

---

## Setup

**1. Get a free Groq API key**

Visit [console.groq.com](https://console.groq.com) — sign up, create key. No credit card required.

**2. Install dependencies**

```bash
git clone https://github.com/FarhanAaqil/self-improving-agent.git
cd self-improving-agent
pip install -r requirements.txt
```

**3. Set your API key**

```bash
# Linux / macOS
export GROQ_API_KEY="your_key_here"

# Windows PowerShell
$env:GROQ_API_KEY = "your_key_here"
```

Or create a `.env` file:

```env
GROQ_API_KEY=your_key_here
```

**4. Run**

```bash
streamlit run app.py
```

---

## Project Structure

```
self-improving-agent/
├── app.py                    ← Streamlit UI (Agent tab + HumanEval tab)
├── config.py                 ← Model name, retry limits, paths
├── sandbox.py                ← subprocess code runner with timeout
├── critique.py               ← Critique agent (second LLM pass)
├── benchmark.py              ← timeit + tracemalloc benchmarking
├── memory.py                 ← ChromaDB vector memory (store + retrieve)
├── evaluate.py               ← HumanEval evaluation engine
├── humaneval_problems.py     ← 20 HumanEval problems
├── requirements.txt
├── memory_db/                ← auto-created: ChromaDB local storage
└── logs/
    ├── attempts.jsonl        ← every generation attempt
    ├── benchmarks.jsonl      ← before/after benchmark results
    └── humaneval_results.jsonl
```

---

## HumanEval Benchmark

We evaluate the self-repairing agent against a canonical 50-problem subset of the OpenAI HumanEval benchmark.

> **Deliberate Scope Decision:** Rather than running the entire 164 problems, evaluating across 50 representative problems was chosen deliberately. It ensures high statistical significance for pass@1 and pass@5 repair dynamics while remaining fully runnable within free-tier API rate limits and practical CI time budgets.

<!-- BENCHMARK_TABLE_START -->
| Metric | Self-Improving Agent | Baseline (Zero-Shot) |
|---|---|---|
| pass@1 | 88.0% | 68.0% (single-pass) |
| pass@5 | 96.0% | 68.0% (no repair) |
| Avg repair attempts | 1.18 | 1.0 (no repair) |
| Avg latency | 62.2 ms | ~50 ms |
<!-- BENCHMARK_TABLE_END -->

---

## How Memory Helps

When a task fails after N retries, the failure (task description + error + final broken code) is embedded and stored in ChromaDB. On the next similar task, the top-k matching failures are retrieved and injected into the generation prompt as negative examples — teaching the agent what patterns to avoid.

---

## Related

This project extends [code-generator-agent](https://github.com/FarhanAaqil/code-generator-agent), which is the base generator + sandbox loop without memory or critique.

---

## Author

**Farhan Aaqil** — B.Tech AI/ML

[![GitHub](https://img.shields.io/badge/GitHub-FarhanAaqil-181717?style=flat&logo=github)](https://github.com/FarhanAaqil)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-farhan--aaqil-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/farhan-aaqil-4730432bb)
