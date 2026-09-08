from groq import Groq

from app.config import GROQ_API_KEY, MODEL

_default_client: Groq | None = None


def _get_client() -> Groq:
    global _default_client
    if _default_client is None:
        _default_client = Groq(api_key=GROQ_API_KEY)
    return _default_client


DOCS_SYSTEM_PROMPT = """You are a senior Python software engineer specializing in clean code and documentation.
Your job is to enrich working Python code with clean, professional PEP 257 docstrings and concise comments.

Rules:
1. Preserve the EXACT logic, behavior, and functionality of the code. Do not change algorithms, variable names, or behavior.
2. Add informative docstrings to all functions and classes (specifying parameters, return types, and brief summary).
3. Return ONLY raw Python code.
4. No markdown formatting, no backticks, no explanations before or after the code."""


def document_code(
    task: str,
    code: str,
    client_override=None,
    model_override: str | None = None,
) -> str:
    """Rewrite working Python code with clean PEP 257 docstrings without changing logic."""
    client = client_override or _get_client()
    model = model_override or MODEL

    prompt = f"""Task:
{task}

Working Python code to document:
{code}

Return the documented Python code."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": DOCS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content.strip()
    return _clean_code(raw)


def _clean_code(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
