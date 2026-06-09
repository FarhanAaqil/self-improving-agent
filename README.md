# 🧠 Self-Improving Code Agent

> An AI agent that writes Python code, executes it in a sandbox, critiques its own output, learns from failures via vector memory, and benchmarks improvement — built on a fully zero-cost stack.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama%203.3%2070B-F55036?style=flat)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
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

Run the **HumanEval tab** in the Streamlit UI to evaluate the agent against 20 standard Python programming problems and compare pass@1 rate against a plain single-call Llama baseline.

| Metric | Self-Improving Agent | Plain Llama (1 call) |
|---|---|---|
| pass@1 | run benchmark → | baseline comparison |
| Avg repair attempts | tracked per run | 1 (no repair) |

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
