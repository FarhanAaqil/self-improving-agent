"""Quality score built from measured data.

Every component is either measured (tests actually executed, coverage traced in the
sandbox, bandit/radon static analysis) or reported by an LLM reviewer. A component
that was skipped is N/A and drops out of the weighted average; it never counts as perfect.
"""

import ast
import re
from typing import Any

WEIGHTS = {
    "tests": 0.25,
    "mutation": 0.15,
    "coverage": 0.10,
    "security": 0.25,
    "complexity": 0.10,
    "performance": 0.15,
}

_BANDIT_PENALTY = {"HIGH": 0.4, "MEDIUM": 0.2, "LOW": 0.05}


def calculate_cyclomatic_complexity(code: str) -> int:
    """McCabe complexity from the AST: 1 + one per decision point (fallback when radon is absent)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 1

    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.IfExp)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, ast.comprehension):
            complexity += 1 + len(node.ifs)
        elif isinstance(node, ast.match_case):
            complexity += 1
    return complexity


def compute_complexity_score(complexity: int) -> float:
    """Normalize McCabe cyclomatic complexity into a 0.0 - 1.0 score."""
    if complexity <= 5:
        return 1.0
    elif complexity <= 10:
        return 0.85
    elif complexity <= 15:
        return 0.70
    elif complexity <= 25:
        return 0.50
    else:
        return max(0.2, round(1.0 - (complexity * 0.02), 2))


def compute_llm_security_score(security_audit: str | None) -> float | None:
    """Score the LLM auditor's tagged findings. None when the audit did not run."""
    if not security_audit:
        return None
    text = security_audit.strip().upper()
    if text.startswith("SECURE"):
        return 1.0

    counts = {tag: len(re.findall(rf"\[{tag}\]", text)) for tag in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    if not any(counts.values()):
        return 0.6  # unstructured warning prose
    score = 1.0 - counts["CRITICAL"] * 0.5 - counts["HIGH"] * 0.3 - counts["MEDIUM"] * 0.15 - counts["LOW"] * 0.05
    return max(0.0, min(1.0, round(score, 2)))


def compute_bandit_score(bandit: dict | None) -> float | None:
    if not bandit or not bandit.get("available"):
        return None
    score = 1.0 - sum(_BANDIT_PENALTY.get(i.get("severity", "").upper(), 0.0) for i in bandit.get("issues", []))
    return max(0.0, round(score, 2))


def compute_performance_score(performance_notes: str | None) -> float | None:
    """Score performance reviewer output. None when the reviewer did not run."""
    if not performance_notes:
        return None
    if performance_notes.strip().upper().startswith("OPTIMIZED"):
        return 1.0
    count = len(re.findall(r"^\s*\d+\.", performance_notes, re.MULTILINE)) or 1
    return max(0.3, round(1.0 - count * 0.15, 2))


def _min_known(*values: float | None) -> float | None:
    known = [v for v in values if v is not None]
    return min(known) if known else None


def calculate_quality_metrics(
    code: str,
    test_report: dict | None = None,
    performance_notes: str | None = None,
    security_audit: str | None = None,
    bandit: dict | None = None,
    radon: dict | None = None,
    generated_tests: str | None = None,
    mutation: dict | None = None,
) -> dict[str, Any]:
    """Combine measured and reviewed signals into a 0-1 overall score with a breakdown."""
    total = (test_report or {}).get("total") or 0
    tests_score = round(test_report["passed"] / total, 2) if total else None
    coverage_score = (test_report or {}).get("coverage") if total else None

    if radon and radon.get("available") and radon.get("max") is not None:
        complexity = int(radon["max"])
    else:
        complexity = calculate_cyclomatic_complexity(code)
    complexity_score = compute_complexity_score(complexity)

    security_score = _min_known(compute_bandit_score(bandit), compute_llm_security_score(security_audit))
    perf_score = compute_performance_score(performance_notes)

    mutation_score = mutation.get("score") if mutation and mutation.get("available") else None

    components = {
        "tests": tests_score,
        "mutation": mutation_score,
        "coverage": coverage_score,
        "security": security_score,
        "complexity": complexity_score,
        "performance": perf_score,
    }
    measured = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in measured)
    overall = round(sum(v * WEIGHTS[k] for k, v in measured.items()) / weight_sum, 2) if weight_sum else None

    bandit_issues = (bandit or {}).get("issues", [])
    return {
        "overall_score": overall,
        "components": components,
        "mutation": mutation,
        "weights": WEIGHTS,
        "cyclomatic_complexity": complexity,
        "complexity_score": complexity_score,
        "tests_passed": (test_report or {}).get("passed"),
        "tests_total": total or None,
        "estimated_coverage": coverage_score,
        "security_score": security_score,
        "performance_score": perf_score,
        "bandit_issues": bandit_issues,
        "radon_blocks": (radon or {}).get("blocks", []),
        "breakdown": {
            "complexity_rating": "A" if complexity_score >= 0.85 else ("B" if complexity_score >= 0.70 else "C"),
            "coverage_pct": int(coverage_score * 100) if coverage_score is not None else None,
            "security_status": "N/A" if security_score is None else ("PASS" if security_score >= 0.85 else "WARN"),
            "performance_status": "N/A" if perf_score is None else ("OPTIMAL" if perf_score >= 0.90 else "REVIEW"),
        },
    }
