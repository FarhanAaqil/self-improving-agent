# ── app/config.py ──────────────────────────────────────────
import os

from dotenv import load_dotenv

# Project root is one level up from app/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load local environment variables from .env if present
load_dotenv(os.path.join(_ROOT, ".env"))


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes", "on")


def _csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ── Environment ─────────────────────────────────────────────
# "production" is the default so a forgotten env var fails closed, not open.
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
IS_DEV = APP_ENV in ("development", "dev", "local", "test")

# ── LLM ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Offline demo / end-to-end test mode: a scripted model, real sandbox (see app/fake_llm.py)
FAKE_LLM = _flag("FAKE_LLM")
MODEL = os.getenv("MODEL", "qwen/qwen3.8-27b")
AVAILABLE_MODELS = _csv(
    "AVAILABLE_MODELS",
    "qwen/qwen3.8-27b,openai/gpt-oss-120b,openai/gpt-oss-20b",
)
if MODEL not in AVAILABLE_MODELS:
    AVAILABLE_MODELS.insert(0, MODEL)

# ── Agent runtime behavior ──────────────────────────────────
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_CRITIQUE_ROUNDS = int(os.getenv("MAX_CRITIQUE_ROUNDS", "3"))
CRITIQUE_CONFIDENCE_THRESHOLD = float(os.getenv("CRITIQUE_CONFIDENCE_THRESHOLD", "0.3"))
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "10"))

# ── Storage & DB ────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", os.path.join(_ROOT, "agent.db"))
LOG_DIR = os.path.join(_ROOT, "logs")  # legacy

# ── Vector Memory (ChromaDB) ────────────────────────────────
MEMORY_ENABLED = _flag("MEMORY_ENABLED", "true")
# Versioned on purpose: an older chromadb can leave a store the current one cannot open
MEMORY_DIR = os.getenv("MEMORY_DIR", os.path.join(_ROOT, "memory_db", "v2"))
MEMORY_COLLECTION = "failures"
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "3"))
# 0.75 threshold: lower thresholds pull semantically unrelated tasks as false-positive context
MEMORY_SIMILARITY_THRESHOLD = float(os.getenv("MEMORY_SIMILARITY_THRESHOLD", "0.75"))
# Hard cap on how much recalled text may enter a prompt
MEMORY_MAX_CHARS = int(os.getenv("MEMORY_MAX_CHARS", "2400"))

# ── Evaluation ───────────────────────────────────────────────
RESULTS_DIR = os.getenv("RESULTS_DIR", os.path.join(_ROOT, "results"))
HUMANEVAL_SUBSET_SIZE = 50

# ── Deployment ───────────────────────────────────────────────
DEMO_MODE = _flag("DEMO_MODE")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "FarhanAaqil/self-improving-agent")
# Repos the PR agent is allowed to write to. The default repo is always allowed.
GITHUB_ALLOWED_REPOS = sorted(set(_csv("GITHUB_ALLOWED_REPOS") + [GITHUB_REPO]))

# ── Security & Hardening ─────────────────────────────────────
API_KEY = os.getenv("API_KEY")
# Extra keys, each its own workspace with separate runs and memory: "alice:key1,team-b:key2"
API_KEYS = os.getenv("API_KEYS", "")
# Callers may send their own Groq key in X-Groq-Key (never stored, never logged)
ALLOW_BYO_GROQ_KEY = _flag("ALLOW_BYO_GROQ_KEY", "true")
# Tokens a workspace may spend per UTC day on runs; 0 disables the cap
DAILY_TOKEN_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", "0"))
# Signs exported verification certificates (HMAC-SHA256); unsigned when empty
CERT_SIGNING_KEY = os.getenv("CERT_SIGNING_KEY", "")
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()  # "json" for structured logs
# Running model output directly on the host is never safe; only for local experiments.
ALLOW_UNSAFE_HOST_SUBPROCESS = _flag("ALLOW_UNSAFE_HOST_SUBPROCESS")
# /execute with caller-supplied code is an arbitrary-code endpoint; off unless asked for.
ALLOW_CODE_OVERRIDE = _flag("ALLOW_CODE_OVERRIDE")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
MAX_CONCURRENT_SANDBOXES = int(os.getenv("MAX_CONCURRENT_SANDBOXES", "4"))
MAX_OUTPUT_CHARS = int(os.getenv("MAX_OUTPUT_CHARS", "65536"))
ALLOWED_ORIGINS = _csv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
)
