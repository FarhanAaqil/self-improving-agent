from groq import Groq

from app.config import GROQ_API_KEY, MODEL

_default_client: Groq | None = None


def _get_client() -> Groq:
    global _default_client
    if _default_client is None:
        _default_client = Groq(api_key=GROQ_API_KEY)
    return _default_client


PERFORMANCE_PROMPT = """You are a performance profiling and algorithm optimization expert.
Review the provided Python code for computational complexity (Big-O time and space), redundant operations, and inefficient data structures.

You must respond with EXACTLY ONE of the following formats:

If the code is already optimal and has no major algorithmic bottlenecks:
OPTIMIZED

OR, if there are genuine performance improvements (e.g. O(n^2) -> O(n), unnecessary memory copies, repeated costly operations):
1. [First specific suggestion with time/space impact]
2. [Second specific suggestion]

Do NOT include any conversational filler, introductory text, markdown headers, or concluding remarks.
Return ONLY "OPTIMIZED" or the numbered list."""


def analyze_performance(
    task: str,
    code: str,
    client_override=None,
    model_override: str | None = None,
) -> str:
    """Analyze code performance and return 'OPTIMIZED' or numbered suggestions, nothing else."""
    client = client_override or _get_client()
    model = model_override or MODEL

    prompt = f"""Task:
{task}

Python Code to analyze:
{code}

Provide your performance evaluation."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PERFORMANCE_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    return _clean_performance_output(raw)


def _clean_performance_output(raw: str) -> str:
    text = raw.strip()
    # Strip backticks if returned
    if text.startswith("`") and text.endswith("`"):
        text = text.strip("`").strip()
    if text.upper().startswith("OPTIMIZED"):
        return "OPTIMIZED"
    return text
