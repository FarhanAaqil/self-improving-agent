# ── config.py ──────────────────────────────────────────────
import os

# ── LLM ──────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "llama-3.3-70b-versatile"
AVAILABLE_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# ── Agent behaviour ───────────────────────────────────────────
MAX_RETRIES = 5
MAX_CRITIQUE_ROUNDS = 3
SANDBOX_TIMEOUT = 10
LOG_DIR = "logs"

# ── Memory (Week 3) ───────────────────────────────────────────
MEMORY_DIR = "memory_db"
MEMORY_COLLECTION = "failures"
MEMORY_TOP_K = 3

# ── Benchmarking (Week 4) ─────────────────────────────────────
BENCHMARK_RUNS = 5        # How many times to run each version for stable timing
BENCHMARK_TIMEOUT = 15    # Max seconds per benchmark run
