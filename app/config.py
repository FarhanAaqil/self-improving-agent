# ── app/config.py ──────────────────────────────────────────
import os

# ── LLM ────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "llama-3.3-70b-versatile"
AVAILABLE_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# ── Agent behaviour ─────────────────────────────────────────
MAX_RETRIES = 3          # plan: default 3 attempts per architecture doc
MAX_CRITIQUE_ROUNDS = 3
CRITIQUE_CONFIDENCE_THRESHOLD = 0.3  # early-stop if confidence below this
SANDBOX_TIMEOUT = 10

# ── Storage paths ───────────────────────────────────────────
# Paths are relative to the project root (one level up from app/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("DB_PATH", os.path.join(_ROOT, "agent.db"))
LOG_DIR = os.path.join(_ROOT, "logs")  # legacy; removed in Day 3 after SQLite migration

# ── Memory (ChromaDB) ────────────────────────────────────────
MEMORY_DIR = os.getenv("MEMORY_DIR", os.path.join(_ROOT, "memory_db"))
MEMORY_COLLECTION = "failures"
MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.75  # Day 8: inject past failures above this threshold

# ── Evaluation ───────────────────────────────────────────────
RESULTS_DIR = os.path.join(_ROOT, "results")
HUMANEVAL_SUBSET_SIZE = 50  # deliberate scope — documented in README

# ── Deployment ───────────────────────────────────────────────
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
