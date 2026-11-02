# ── app/critique.py ─────────────────────────────────────────
# Two different jobs that used to share one prompt:
#   diagnose_failure()  — after a failed attempt: why it broke, how to fix it,
#                         and how likely another attempt is to succeed.
#   critique_code()     — after verification passed: an approval/rewrite review.

import json
import re

from app import llm

DIAGNOSE_SYSTEM_PROMPT = """You are debugging a failed attempt at a Python task.
You get the task, the code, and what happened when it ran against the spec tests.

Reply with ONE JSON object and nothing else:
{
  "summary": "one short sentence a non-expert can read, first person, e.g. 'My loop crashes on an empty list.'",
  "root_cause": "the precise technical cause",
  "fix_plan": "concrete instructions for the next attempt",
  "blame": "code" or "tests",
  "retry_confidence": number between 0 and 1
}

Rules:
- blame is "tests" only when a test clearly contradicts the task statement.
- retry_confidence below 0.3 means the task is impossible or contradictory as written.
- Never include code in the JSON values."""

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

Most correct, clean code should have confidence >= 0.8 and VERDICT: APPROVED."""


def diagnose_failure(
    task: str,
    code: str,
    feedback: str,
    tests: str | None = None,
    client_override=None,
    model_override: str | None = None,
) -> dict:
    """
    Explain a failed attempt.
    Returns: { summary, root_cause, fix_plan, blame, confidence, reasoning, raw }
    `confidence` is the estimated chance that another attempt succeeds.
    """
    user = (
        f"Task:\n{task}\n\n"
        f"Code that was run:\n{code}\n\n"
        + (f"Spec tests:\n{tests}\n\n" if tests else "")
        + f"What happened:\n{feedback}"
    )
    raw = llm.chat(
        [
            {"role": "system", "content": DIAGNOSE_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        model=model_override,
        temperature=0.1,
        max_tokens=600,
        client=client_override,
    )
    return _parse_diagnosis(raw)


def _parse_diagnosis(raw: str) -> dict:
    data: dict = {}
    match = re.search(r"\{.*\}", raw or "", re.S)
    if match:
        try:
            data = json.loads(match.group(0))
        except ValueError:
            data = {}

    try:
        confidence = float(data.get("retry_confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))

    summary = str(data.get("summary") or "").strip() or "That attempt failed; trying a different fix."
    root_cause = str(data.get("root_cause") or "").strip()
    fix_plan = str(data.get("fix_plan") or "").strip()
    blame = "tests" if str(data.get("blame", "code")).lower().startswith("test") else "code"
    return {
        "summary": summary,
        "root_cause": root_cause,
        "fix_plan": fix_plan,
        "blame": blame,
        "confidence": round(confidence, 2),
        "reasoning": summary + (f" Root cause: {root_cause}" if root_cause else ""),
        "raw": raw,
    }


def critique_code(task: str, code: str, output: str, client_override=None, model_override=None) -> dict:
    """
    Review code that already passed verification.
    Returns: { verdict, confidence, reasoning, issues, instructions, raw }
    """
    user_message = f"""Task the code was written for:
{task}

Working code to review:
{code}

Actual output produced:
{output or "(no output — code ran silently)"}

Review this code and give your verdict with confidence score."""

    raw = llm.chat(
        [
            {"role": "system", "content": CRITIQUE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        model=model_override,
        temperature=0.2,
        max_tokens=1024,
        client=client_override,
    )
    return _parse_verdict(raw)


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
