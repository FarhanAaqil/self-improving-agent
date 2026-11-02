from app import llm

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
    prompt = f"""Task:
{task}

Working Python code to document:
{code}

Return the documented Python code."""

    raw = llm.chat(
        [
            {"role": "system", "content": DOCS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=model_override,
        temperature=0.1,
        max_tokens=2048,
        client=client_override,
    )
    return _clean_code(raw)


def _clean_code(raw: str) -> str:
    return llm.clean_code(raw)
