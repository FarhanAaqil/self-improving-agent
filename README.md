# Self-Improving Code Agent

> An AI agent that writes Python code, executes it in a sandbox, critiques its own output, learns from past failures via vector memory, and benchmarks improvement — built entirely on a zero-cost stack.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama%203.3%2070B-F55036?style=flat)](https://console.groq.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/Memory-ChromaDB-orange?style=flat)](https://www.trychroma.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## What It Does

The agent takes a natural-language coding task and runs a full Generate → Execute → Critique → Learn loop:

1. **Generator** — Llama 3.3 70B writes a Python solution via the Groq API
2. **Sandbox** — The code runs in an isolated subprocess; errors loop back to the generator for auto-repair
3. **Critique Agent** — A second, independent LLM pass reviews the working code for efficiency, edge cases, and redundancy
4. **Vector Memory** — Failures and solutions are stored in ChromaDB (local); future tasks retrieve semantically similar past attempts as context, so the agent genuinely learns
5. **Benchmarker** — `timeit` + `tracemalloc` measure runtime and memory before and after critique, making improvement quantifiable
6. **HumanEval** — A built-in evaluation suite runs 20 HumanEval problems to benchmark pass@1 against a plain Llama baseline

---

## Architecture

```
User Task
    │
    ▼
┌─────────────────────┐
│  🧠 Memory Lookup   │  ChromaDB retrieves similar past failures
│    (memory.py)      │  and injects them as context
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ⚙️ Generator Agent │  Llama 3.3 70B writes Python code
│   (app.py core)     │  Sandbox runs it — errors loop back to fix
└──────────┬──────────┘
           │ working code
           ▼
┌─────────────────────┐
│  🔍 Critique Agent  │  Second independent LLM call reviews for
│   (critique.py)     │  efficiency, edge cases, redundancy
└──────────┬──────────┘
           │ approved code
           ▼
┌─────────────────────┐
│  📊 Benchmark       │  timeit + tracemalloc measures
│  (benchmark.py)     │  runtime + memory before/after critique
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  💾 Memory Store    │  Outcome (pass/fail + solution) saved
│    (memory.py)      │  to ChromaDB for future context
└─────────────────────┘
```

---

## Zero-Cost Stack

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq API — Llama 3.3 70B | Free tier |
| Code sandbox | Python `subprocess` | Free |
| Vector memory | ChromaDB (local) | Free |
| Embeddings | `sentence-transformers` (local) | Free |
| Benchmarking | `timeit` + `tracemalloc` (stdlib) | Free |
| UI | Streamlit | Free |

No OpenAI. No paid APIs. No cloud database.

---

## Project Structure

```
self-improving-agent/
├── app.py                    ← Streamlit UI (Agent tab + HumanEval tab)
├── config.py                 ← All settings (model name, ChromaDB path, prompts)
├── sandbox.py                ← Subprocess code runner with timeout + error capture
├── critique.py               ← Critique agent (second LLM pass)
├── benchmark.py              ← timeit + tracemalloc benchmarking
├── memory.py                 ← ChromaDB vector memory (store + retrieve)
├── evaluate.py               ← HumanEval evaluation engine
├── humaneval_problems.py     ← 20 HumanEval problems with test cases
├── requirements.txt
├── runtime.txt               ← Python version pin
├── memory_db/                ← auto-created: ChromaDB persistent storage
└── logs/
    ├── attempts.jsonl        ← every generation attempt logged
    ├── benchmarks.jsonl      ← benchmark results
    └── humaneval_results.jsonl
```

---

## Setup

### 1. Get a free Groq API key

Visit [console.groq.com](https://console.groq.com) — sign up, create a key. No credit card required.

### 2. Clone and install

```bash
git clone https://github.com/FarhanAaqil/self-improving-agent.git
cd self-improving-agent
pip install -r requirements.txt
```

### 3. Set your API key

```bash
# Linux / macOS
export GROQ_API_KEY="your_key_here"

# Windows (PowerShell)
$env:GROQ_API_KEY = "your_key_here"
```

Or create a `.env` file:

```
GROQ_API_KEY=your_key_here
```

### 4. Run

```bash
streamlit run app.py
```

Open the local Streamlit URL shown in the terminal.

---

## Usage

**Agent Tab** — Type any Python coding task in natural language. The agent generates, runs, critiques, and stores the result. Past failures are retrieved automatically as context.

**HumanEval Tab** — Click "Run Benchmark" to evaluate the agent against 20 HumanEval problems and compare pass@1 against a plain single-call Llama baseline.

Example prompts:
```
Write a function that checks if a string is a palindrome
Implement binary search on a sorted list
Write a function to find all prime numbers up to n using the Sieve of Eratosthenes
Merge two sorted lists into one sorted list
```

---

## Weekly Build Log

| Week | Feature Added | Key File |
|---|---|---|
| 1 | Generator + subprocess sandbox loop | `sandbox.py` |
| 2 | Critique agent (second LLM pass) | `critique.py` |
| 3 | ChromaDB vector memory | `memory.py` |
| 4 | Benchmarking (timeit + tracemalloc) | `benchmark.py` |
| 5 | HumanEval evaluation suite | `evaluate.py` |

---

## HumanEval Results

| Metric | Agent (with critique + memory) | Baseline (plain Llama) |
|---|---|---|
| pass@1 | Run benchmark to generate | 1 attempt per problem |
| Avg fix attempts | Logged in `attempts.jsonl` | — |

*Run the HumanEval tab in the Streamlit UI to generate your own numbers.*

---

## Author

**Farhan Aaqil Durrani**
B.Tech AI/ML — JPNCE Mahbubnagar, Telangana

[![GitHub](https://img.shields.io/badge/GitHub-FarhanAaqil-181717?style=flat&logo=github)](https://github.com/FarhanAaqil)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-farhan--aaqil-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/farhan-aaqil-4730432bb)
