# ── app/critique.py ─────────────────────────────────────────
# Critique Agent.
# Moved from root critique.py into app/ with updated imports.
# NOTE: this version still returns APPROVED/REWRITE verdict only.
# Day 7 upgrades it to also return a confidence score (0.0–1.0)
# for the adaptive early-stop feature.

from groq import Groq

from app.config import GROQ_API_KEY, MODEL

# Lazy — not instantiated at import time so the module is safe to import
# in tests and CI environments without GROQ_API_KEY set.
_default_client: Groq | None = None


def _get_client() -> Groq:
    global _default_client
    if _default_client is None:
        _default_client = Groq(api_key=GROQ_API_KEY)
    return _default_client

CRITIQUE_SYSTEM_PROMPT = """You are a senior Python code reviewer.

Your job is to review working Python code, assign a confidence score, and decide if it needs improvement.

You must respond in this EXACT format:

VERDICT: APPROVED
CONFIDENCE: [float between 0.0 and 1.0, e.g. 0.95]
REASONING: [Brief explanation of why the code is approved]

OR:

VERDICT: REWRITE
CONFIDENCE: [float between 0.0 and 1.0 estimating likelihood a retry will succeed, e.g. 0.65]
REASONING: [Brief explanation of the core deficiency]
ISSUES:
- [specific issue 1]
- [specific issue 2]
REWRITE_INSTRUCTIONS:
[Concrete instructions for the generator to fix these issues]

Review criteria — flag only real problems, not style preferences:
1. Algorithm efficiency — is there a clearly better approach? (e.g. O(n^2) when O(n) is easy)
2. Redundant code — unnecessary loops, variables, or repeated logic
3. Missing edge cases — empty input, division by zero, index out of bounds
4. Readability — deeply nested logic that can be flattened cleanly
5. Incorrect output — does it actually print/return what the task asked for?

If an intractable architectural error or impossible specification is present, assign confidence < 0.3.
Most correct, clean code should have confidence >= 0.8 and VERDICT: APPROVED."""


def critique_code(task: str, code: str, output: str, client_override=None, model_override=None) -> dict:
    """
    Critique a working piece of code.
    Returns: { verdict, confidence, reasoning, issues, instructions, raw }
    """
    _client = client_override or _get_client()
    _model = model_override or MODEL

    user_message = f"""Task the code was written for:
{task}

Working code to review:
{code}

Actual output produced:
{output or "(no output — code ran silently)"}

Review this code and give your verdict with confidence score."""

    response = _client.chat.completions.create(
        model=_model,
        messages=[
            {"role": "system", "content": CRITIQUE_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    return _parse_verdict(raw)


def critique_rewrite(task: str, code: str, instructions: str, client_override=None, model_override=None) -> str:
    """
    Ask the generator to rewrite code based on critique instructions.
    Returns only the raw improved Python code string.
    """
    _client = client_override or _get_client()
    _model = model_override or MODEL

    response = _client.chat.completions.create(
        model=_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert Python programmer.\n"
                    "Return ONLY raw Python code. No markdown. No backticks. No explanations.\n"
                    "The code must be complete and runnable as-is."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Current working code:\n{code}\n\n"
                    f"A code reviewer flagged these issues:\n{instructions}\n\n"
                    f"Rewrite the code fixing all issues. Return only the improved Python code."
                ),
            },
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def _parse_verdict(raw: str) -> dict:
    """Parse the structured verdict, confidence score, and instructions from the critique LLM."""
    result = {
        "verdict": "APPROVED",
        "confidence": 0.85,
        "reasoning": "",
        "issues": [],
        "instructions": "",
        "raw": raw,
    }

    lines = raw.splitlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("VERDICT:"):
            verdict_text = stripped.split("VERDICT:")[-1].strip().upper()
            result["verdict"] = "REWRITE" if "REWRITE" in verdict_text else "APPROVED"
        elif stripped.startswith("CONFIDENCE:"):
            val_str = stripped.split("CONFIDENCE:")[-1].strip()
            try:
                # Parse numeric float (e.g. 0.85, 85%)
                clean_val = val_str.replace("%", "").strip()
                parsed = float(clean_val)
                if parsed > 1.0:
                    parsed = parsed / 100.0
                result["confidence"] = max(0.0, min(1.0, round(parsed, 2)))
            except ValueError:
                result["confidence"] = 0.5 if result["verdict"] == "REWRITE" else 0.85
        elif stripped.startswith("REASONING:"):
            result["reasoning"] = stripped.split("REASONING:")[-1].strip()

    if result["verdict"] == "REWRITE":
        in_issues = False
        in_instructions = False
        instruction_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ISSUES:"):
                in_issues, in_instructions = True, False
                continue
            if stripped.startswith("REWRITE_INSTRUCTIONS:"):
                in_issues, in_instructions = False, True
                continue
            if in_issues and stripped.startswith("-"):
                result["issues"].append(stripped[1:].strip())
            if in_instructions and stripped:
                instruction_lines.append(stripped)

        result["instructions"] = "\n".join(instruction_lines)

    return result
