"""Deterministic stand-in for Groq, enabled with FAKE_LLM=true.

It exists so the whole pipeline (spec tests, a failing first attempt, diagnosis, repair,
review, docs) can be demonstrated and end-to-end tested without an API key. Everything
it "writes" is real Python that really runs in the sandbox; only the model is scripted.
"""

import json
import re

_SOLVED = '''def add(a, b):
    """Return the sum of a and b."""
    return a + b
'''

_BUGGY = '''def add(a, b):
    return a - b
'''

_TESTS = '''def test_adds_positive_numbers():
    assert add(2, 3) == 5, "2 + 3 should be 5"


def test_adds_negative_numbers():
    assert add(-4, 1) == -3, "-4 + 1 should be -3"


def test_zero_is_identity():
    assert add(7, 0) == 7, "adding zero changes nothing"
'''


def _function_name(task: str) -> str:
    match = re.search(r"\b([a-z_][a-z0-9_]*)\s*\(", task)
    return match.group(1) if match else "add"


def respond(messages: list[dict]) -> str:
    system = messages[0]["content"] if messages else ""
    user = messages[-1]["content"] if messages else ""
    name = _function_name(user.split("Task:", 1)[-1] if "Task:" in user else user)
    rename = (lambda code: code.replace("add", name)) if name != "add" else (lambda code: code)

    if "spec for code that does not exist yet" in system:
        return rename(_TESTS)
    if "hardening a test suite" in system:
        return "NONE"
    if "debugging a failed attempt" in system:
        return json.dumps({
            "summary": "I subtracted where the task asks for a sum.",
            "root_cause": "The function returns a - b instead of a + b.",
            "fix_plan": "Return a + b.",
            "blame": "code",
            "retry_confidence": 0.9,
        })
    if "senior Python code reviewer" in system:
        return "VERDICT: APPROVED\nCONFIDENCE: 0.95\nREASONING: Minimal and correct."
    if "performance profiling" in system:
        return "OPTIMIZED"
    if "security auditor" in system:
        return "SECURE"
    if "PEP 257" in system:
        return rename(_SOLVED)
    if "QA engineer" in system:
        return rename(_TESTS)
    # Generator: the first attempt is wrong on purpose, any repair gets it right
    return rename(_SOLVED if "previous attempt" in user else _BUGGY)
