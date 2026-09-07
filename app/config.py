# ── app/config.py ──────────────────────────────────────────
import os
from dotenv import load_dotenv

# Project root is one level up from app/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load local environment variables from .env if present
load_dotenv(os.path.join(_ROOT, ".env"))

# ── LLM ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")
AVAILABLE_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# ── Agent runtime behavior ──────────────────────────────────
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_CRITIQUE_ROUNDS = int(os.getenv("MAX_CRITIQUE_ROUNDS", "3"))
CRITIQUE_CONFIDENCE_THRESHOLD = float(os.getenv("CRITIQUE_CONFIDENCE_THRESHOLD", "0.3"))
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "10"))

# ── Storage & DB ────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", os.path.join(_ROOT, "agent.db"))
LOG_DIR = os.path.join(_ROOT, "logs")  # legacy

# ── Vector Memory (ChromaDB) ────────────────────────────────
MEMORY_DIR = os.getenv("MEMORY_DIR", os.path.join(_ROOT, "memory_db"))
MEMORY_COLLECTION = "failures"
MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.75

# ── Evaluation ───────────────────────────────────────────────
RESULTS_DIR = os.path.join(_ROOT, "results")
HUMANEVAL_SUBSET_SIZE = 50

# ── Deployment ───────────────────────────────────────────────
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
