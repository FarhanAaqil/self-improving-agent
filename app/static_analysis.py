"""Deterministic static analysis of generated code: bandit for security, radon for complexity.

Neither tool executes the code, so running them on the host is safe.
Both are optional at runtime: if a tool is missing the result says so instead of failing.
"""

import logging
import os
import tempfile

logger = logging.getLogger("self_improving_agent.static")


def bandit_scan(code: str) -> dict:
    """Return {'available': bool, 'issues': [{severity, confidence, test_id, text, line}]}."""
    try:
        from bandit.core import config as b_config
        from bandit.core import manager as b_manager
    except ImportError:
        return {"available": False, "issues": []}

    fd, path = tempfile.mkstemp(suffix=".py", prefix="bandit-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        manager = b_manager.BanditManager(b_config.BanditConfig(), "file", quiet=True)
        manager.discover_files([path])
        manager.run_tests()
        issues = [
            {
                "severity": str(issue.severity),
                "confidence": str(issue.confidence),
                "test_id": issue.test_id,
                "text": issue.text,
                "line": issue.lineno,
            }
            for issue in manager.get_issue_list()
        ]
        return {"available": True, "issues": issues}
    except Exception as e:  # a parse error in generated code shouldn't break the run
        logger.warning("bandit scan failed: %s", e)
        return {"available": True, "issues": [], "error": str(e)}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def radon_complexity(code: str) -> dict:
    """Return {'available': bool, 'max': int, 'average': float, 'blocks': [{name, complexity, rank}]}."""
    try:
        from radon.complexity import cc_rank, cc_visit
    except ImportError:
        return {"available": False, "max": None, "average": None, "blocks": []}

    try:
        blocks = cc_visit(code)
    except Exception as e:
        return {"available": True, "max": None, "average": None, "blocks": [], "error": str(e)}

    items = [
        {"name": b.name, "complexity": b.complexity, "rank": cc_rank(b.complexity)}
        for b in blocks
    ]
    if not items:
        return {"available": True, "max": 1, "average": 1.0, "blocks": []}
    values = [i["complexity"] for i in items]
    return {
        "available": True,
        "max": max(values),
        "average": round(sum(values) / len(values), 2),
        "blocks": sorted(items, key=lambda i: -i["complexity"])[:10],
    }
