from groq import Groq

from app.config import GROQ_API_KEY, MODEL

_default_client: Groq | None = None


def _get_client() -> Groq:
    global _default_client
    if _default_client is None:
        _default_client = Groq(api_key=GROQ_API_KEY)
    return _default_client


TEST_AGENT_PROMPT = """You are a senior QA engineer and Python test specialist.
Your task is to write clean, complete unit tests using pytest for the given Python code.

Requirements:
- Define comprehensive test functions prefixed with `test_`
- Cover common happy paths and boundary edge cases (empty collections, zero, negative numbers, extreme inputs)
- Use standard `assert` statements
- Return ONLY runnable Python code. No markdown fences, no explanations, no backticks."""


def generate_unit_tests(
    task: str,
    code: str,
    client_override=None,
    model_override: str | None = None,
) -> str:
    """Take approved code and task, generate unit tests, and return them as a string."""
    client = client_override or _get_client()
    model = model_override or MODEL

    prompt = f"""Task:
{task}

Approved Python Code:
{code}

Write standalone pytest unit tests testing this code."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TEST_AGENT_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
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
