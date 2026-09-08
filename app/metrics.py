import ast
import re
from typing import Any


def calculate_cyclomatic_complexity(code: str) -> int:
    """
    Calculate McCabe cyclomatic complexity of Python source code using AST.
    Base complexity starts at 1, increasing with each branching / decision node.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 1

    complexity = 1
    for node in ast.walk(tree):
        # Decision points in Python AST
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.Assert, ast.With, ast.AsyncWith)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            # Each binary boolean operand (and, or) introduces an alternate branch path
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # Add for each 'if' clause inside comprehensions
            for gen in node.generators:
                complexity += len(gen.ifs)
        elif isinstance(node, ast.IfExp):  # Ternary expression
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


def compute_estimated_coverage(code: str, generated_tests: str | None) -> float:
    """
    Estimate test coverage by checking how many functions/classes in code
    are targeted by assertions in generated_tests.
    """
    if not generated_tests or not generated_tests.strip():
        return 0.0

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0.5

    defined_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    ]

    if not defined_names:
        # Code is top-level script, check if test file contains assert
        return 0.9 if "assert" in generated_tests else 0.4

    covered_count = sum(1 for name in defined_names if name in generated_tests)
    ratio = covered_count / len(defined_names)
    # Check for assert statements in the tests
    has_asserts = "assert" in generated_tests
    multiplier = 1.0 if has_asserts else 0.5
    return round(min(1.0, max(0.1, ratio * multiplier)), 2)


def compute_security_score(security_audit: str | None) -> float:
    """Calculate security score from CodeSecurityAudit text output."""
    if not security_audit:
        return 1.0
    text = security_audit.strip().upper()
    if text.startswith("SECURE"):
        return 1.0

    score = 1.0
    critical_count = len(re.findall(r"\[CRITICAL\]", text))
    high_count = len(re.findall(r"\[HIGH\]", text))
    medium_count = len(re.findall(r"\[MEDIUM\]", text))
    low_count = len(re.findall(r"\[LOW\]", text))

    score -= (critical_count * 0.5)
    score -= (high_count * 0.3)
    score -= (medium_count * 0.15)
    score -= (low_count * 0.05)

    if critical_count == 0 and high_count == 0 and medium_count == 0 and low_count == 0:
        # Unstructured vulnerability note
        score = 0.6

    return max(0.0, min(1.0, round(score, 2)))


def compute_performance_score(performance_notes: str | None) -> float:
    """Calculate performance score from performance_agent output."""
    if not performance_notes:
        return 1.0
    text = performance_notes.strip().upper()
    if text.startswith("OPTIMIZED"):
        return 1.0

    # Count numbered suggestions (e.g. "1.", "2.", etc.)
    suggestion_matches = re.findall(r"^\s*\d+\.", performance_notes, re.MULTILINE)
    count = len(suggestion_matches)
    if count == 0:
        count = 1  # At least one suggestion present

    score = max(0.3, round(1.0 - (count * 0.15), 2))
    return score


def calculate_quality_metrics(
    code: str,
    generated_tests: str | None = None,
    performance_notes: str | None = None,
    security_audit: str | None = None,
) -> dict[str, Any]:
    """
    Compute comprehensive quality metrics across complexity, test coverage,
    security review, and performance profiling.
    """
    complexity = calculate_cyclomatic_complexity(code)
    complexity_score = compute_complexity_score(complexity)
    coverage_score = compute_estimated_coverage(code, generated_tests)
    security_score = compute_security_score(security_audit)
    perf_score = compute_performance_score(performance_notes)

    # Weighted overall score (out of 1.0):
    # 25% complexity, 25% test coverage, 30% security, 20% performance
    overall_score = round(
        (complexity_score * 0.25)
        + (coverage_score * 0.25)
        + (security_score * 0.30)
        + (perf_score * 0.20),
        2,
    )

    return {
        "cyclomatic_complexity": complexity,
        "complexity_score": complexity_score,
        "estimated_coverage": coverage_score,
        "security_score": security_score,
        "performance_score": perf_score,
        "overall_score": overall_score,
        "breakdown": {
            "complexity_rating": "A" if complexity_score >= 0.85 else ("B" if complexity_score >= 0.70 else "C"),
            "coverage_pct": int(coverage_score * 100),
            "security_status": "PASS" if security_score >= 0.85 else "WARN",
            "performance_status": "OPTIMAL" if perf_score >= 0.90 else "REVIEW",
        },
    }
