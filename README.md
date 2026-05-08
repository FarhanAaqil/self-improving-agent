# Self-Improving Code Agent

An AI agent that writes Python code, runs it, critiques its own solutions, learns from failures using vector memory, and benchmarks improvement — built entirely on a zero-cost stack.

## Architecture

```
User Task
    │
    ▼
┌─────────────────────┐
│  🧠 Memory Lookup   │  ChromaDB retrieves similar past failures
│  (Week 3)           │  and injects them as context
└──────────┬──────────┘
           │
    ▼
┌─────────────────────┐
│  ⚙️ Generator Agent │  Llama 3.3 70B writes Python code
│  (Week 1)           │  Sandbox runs it — errors loop back to fix
└──────────┬──────────┘
           │ working code
    ▼
┌─────────────────────┐
│  🔍 Critique Agent  │  Second independent LLM reviews for
│  (Week 2)           │  efficiency, edge cases, redundancy
└──────────┬──────────┘
           │ approved code
    ▼
┌─────────────────────┐
│  📊 Benchmark       │  timeit + tracemalloc measures
│  (Week 4)           │  runtime + memory before/after critique
└─────────────────────┘
```

## Zero-cost stack

| Component     | Tool                          | Cost |
| ------------- | ----------------------------- | ---- |
| LLM           | Groq API — Llama 3.3 70B      | Free |
| Code sandbox  | Python subprocess             | Free |
| Vector memory | ChromaDB (local)              | Free |
| Embeddings    | sentence-transformers (local) | Free |
| Benchmarking  | timeit + tracemalloc (stdlib) | Free |
| UI            | Streamlit                     | Free |

## Setup

**1. Get free Groq API key**
Visit https://console.groq.com — sign up, create key. No credit card.

**2. Install dependencies**

```bash
pip install groq streamlit chromadb sentence-transformers
```

**3. Set API key**

```bash
export GROQ_API_KEY="your_key_here"
```

**4. Run**

```bash
streamlit run app.py
```

## Project structure

```
code_agent/
├── app.py                   ← Streamlit UI (Agent + HumanEval tabs)
├── config.py                ← All settings
├── generator.py             ← CLI: LLM code generation
├── sandbox.py               ← Subprocess code runner
├── critique.py              ← Critique agent
├── benchmark.py             ← timeit + tracemalloc benchmarking
├── memory.py                ← ChromaDB vector memory
├── evaluate.py              ← HumanEval evaluation engine
├── humaneval_problems.py    ← 20 HumanEval problems
├── main.py                  ← CLI entry point
├── requirements.txt
├── memory_db/               ← auto-created: ChromaDB storage
└── logs/
    ├── attempts.jsonl       ← every generation attempt
    ├── benchmarks.jsonl     ← benchmark results
    └── humaneval_results.jsonl ← HumanEval run history
```

## HumanEval Results

|              | Agent                | Baseline (plain Llama) |
| ------------ | -------------------- | ---------------------- |
| pass@1       | Run benchmark to see | Run benchmark to see   |
| Avg attempts | —                    | 1 (single call)        |

_Run the HumanEval tab in the UI to generate your own numbers._

## Weekly build log

| Week | Feature                  | Key file       |
| ---- | ------------------------ | -------------- |
| 1    | Generator + sandbox loop | `sandbox.py`   |
| 2    | Critique agent           | `critique.py`  |
| 3    | Vector memory            | `memory.py`    |
| 4    | Benchmarking             | `benchmark.py` |
| 5    | HumanEval benchmark      | `evaluate.py`  |

## Author

Farhan Aaqil Durrani — github.com/FarhanAaqil
