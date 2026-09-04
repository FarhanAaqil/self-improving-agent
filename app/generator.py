# ── app/generator.py ────────────────────────────────────────
# Generation layer: prompt construction + Groq LLM calls.
# ChromaDB few-shot retrieval is wired in on Day 8.
# For now this is a clean extraction of the generation logic
# that was embedded in app.py — no functional change yet.

from groq import Groq
from app.config import GROQ_API_KEY, MODEL

SYSTEM_PROMPT = """You are an expert Python programmer.
Return ONLY raw Python code. No markdown. No backticks. No explanations.
Code must be complete and runnable. Do not use input(). Only use standard library."""


def build_messages(task: str, error: str | None = None, attempt: int = 1, memory_context: str = "") -> list[dict]:
    """
    Construct the message list for the LLM.
    - attempt 1: fresh generation (with optional memory context injected)
    - attempt > 1: repair — includes the previous traceback
    """
    system = SYSTEM_PROMPT + (f"\n\n{memory_context}" if memory_context else "")
    msgs = [{"role": "system", "content": system}]

    if error and attempt > 1:
        msgs.append({
            "role": "user",
            "content": (
                f"Task: {task}\n\n"
                f"Attempt {attempt - 1} failed with this error:\n{error}\n\n"
                f"Fix it. Return only corrected Python code."
            ),
        })
    else:
        msgs.append({
            "role": "user",
            "content": f"Task: {task}\n\nWrite Python code to solve this.",
        })

    return msgs


def generate_code(
    task: str,
    error: str | None = None,
    attempt: int = 1,
    memory_context: str = "",
    model: str = MODEL,
    api_key: str | None = None,
) -> str:
    """
    Call the LLM and return the generated Python code string.
    Raises on LLM error — callers should catch.
    """
    client = Groq(api_key=api_key or GROQ_API_KEY)
    messages = build_messages(task, error, attempt, memory_context)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=2048,
    )
    raw = response.choices[0].message.content.strip()
    return _clean_code(raw)


def _clean_code(raw: str) -> str:
    # Models occasionally wrap in ```python fences despite prompt instructions.
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
