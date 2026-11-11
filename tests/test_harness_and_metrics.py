"""The verification harness (needs Docker), quality metrics, static analysis and memory helpers."""

from unittest.mock import MagicMock

import pytest

from app.harness import verify
from app.memory import error_signature, format_memories, list_memories
from app.metrics import calculate_quality_metrics
from app.sandbox import _is_docker_available
from app.static_analysis import bandit_scan, radon_complexity

needs_docker = pytest.mark.skipif(not _is_docker_available(), reason="Docker daemon not running")

SOLUTION = '''
def add(a, b):
    if a < 0:
        return -1
    return a + b
'''


@needs_docker
@pytest.mark.sandbox
def test_harness_counts_tests_and_measures_coverage():
    tests = "def test_basic():\n    assert add(1, 2) == 3\n\ndef test_wrong():\n    assert add(2, 2) == 5, 'nope'\n"
    v = verify(SOLUTION, tests)
    assert not v.success
    assert (v.passed, v.total) == (1, 2)
    assert 0 < v.coverage < 1
    assert v.failures[0]["test"] == "test_wrong"
    assert "Tests passed: 1/2" in v.feedback()


@needs_docker
@pytest.mark.sandbox
def test_harness_passes_only_when_every_test_passes():
    v = verify(SOLUTION, "def test_basic():\n    assert add(1, 2) == 3\n")
    assert v.success and v.sandboxed and v.total == 1


@needs_docker
@pytest.mark.sandbox
def test_harness_reports_crashes_and_syntax_errors():
    assert "SyntaxError" in verify("def f(:\n  pass", "def test_x(): pass").solution_error
    assert "ValueError" in verify("raise ValueError('x')").solution_error


@needs_docker
@pytest.mark.sandbox
def test_solution_cannot_forge_a_report_with_a_guessed_marker():
    forged = 'print("\\n__AGENT_REPORT_0000000000000000__{\\"total\\": 9, \\"passed\\": 9}")\nraise SystemExit(1)'
    assert not verify(forged, "def test_x():\n    assert False\n").success


def test_metrics_mark_skipped_components_as_not_applicable():
    metrics = calculate_quality_metrics("def f():\n    return 1\n")
    assert metrics["components"]["tests"] is None
    assert metrics["components"]["security"] is None
    assert metrics["breakdown"]["security_status"] == "N/A"
    # Only complexity was measured, so the score is that alone, not padded with free 1.0s
    assert metrics["overall_score"] == metrics["complexity_score"]


def test_metrics_penalise_failing_tests_and_bandit_findings():
    good = calculate_quality_metrics(
        "def f(): return 1", test_report={"total": 4, "passed": 4, "coverage": 1.0},
        bandit={"available": True, "issues": []}, security_audit="SECURE",
    )
    bad = calculate_quality_metrics(
        "def f(): return 1", test_report={"total": 4, "passed": 2, "coverage": 0.5},
        bandit={"available": True, "issues": [{"severity": "HIGH"}]}, security_audit="SECURE",
    )
    assert good["overall_score"] > bad["overall_score"]
    assert bad["security_score"] == 0.6


def test_static_analysis_finds_shell_injection_and_complexity():
    code = "import subprocess\ndef run(c):\n    if c:\n        return subprocess.call(c, shell=True)\n"
    assert any(i["test_id"] == "B602" for i in bandit_scan(code)["issues"])
    assert radon_complexity(code)["max"] == 2


def test_error_signature_is_stable_across_numbers():
    a = error_signature('Traceback...\n  File "x", line 12\nIndexError: list index 5 out of range')
    b = error_signature('Traceback...\n  File "x", line 99\nIndexError: list index 7 out of range')
    assert a == b and a.startswith("IndexError")


def test_lessons_render_as_what_broke_and_what_fixed_it():
    text = format_memories([{"kind": "fix", "task": "parse csv", "error": "KeyError: 'id'",
                             "lesson": "Use dict.get for optional columns", "code": "", "similarity": 0.9}])
    assert "What fixed it: Use dict.get" in text


def test_list_memories_puts_pinned_first_then_newest():
    coll = MagicMock()
    coll.get.return_value = {
        "ids": ["old", "new", "pinned"],
        "metadatas": [
            {"timestamp": "2026-01-01", "pinned": False},
            {"timestamp": "2026-03-01", "pinned": False},
            {"timestamp": "2025-01-01", "pinned": True},
        ],
    }
    items = list_memories(collection=coll)["items"]
    assert [i["id"] for i in items] == ["pinned", "new", "old"]


def test_unopenable_memory_store_degrades_to_503_not_500():
    """An old or corrupt vector store must never crash requests or runs."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app import memory
    from app.main import app

    def boom(*args, **kwargs):
        raise ValueError("Could not connect to tenant default_tenant")

    with patch("app.main.MEMORY_ENABLED", True), patch("chromadb.PersistentClient", boom):
        memory._client = memory._collection = None
        resp = TestClient(app).get("/memory/search", params={"q": "anything at all"})
        assert resp.status_code == 503
        assert "could not be opened" in resp.json()["detail"]
        assert "ValueError" in resp.json()["detail"]
    memory._client = memory._collection = None


@needs_docker
@pytest.mark.sandbox
def test_mutation_testing_tells_weak_tests_from_strong_ones():
    from app.harness import mutation_test

    solution = "def is_adult(age):\n    return age >= 18\n"
    weak = mutation_test(solution, "def test_grown():\n    assert is_adult(40)\n")
    strong = mutation_test(
        solution,
        "def test_grown():\n    assert is_adult(40)\n"
        "def test_boundary():\n    assert is_adult(18) and not is_adult(17)\n",
    )
    assert weak["available"] and weak["survivors"], weak
    assert strong["score"] == 1.0 and not strong["survivors"]
    assert weak["score"] < strong["score"]
    assert "18" in weak["survivors"][0]["source"]


@needs_docker
@pytest.mark.sandbox
def test_mutation_testing_refuses_a_failing_baseline_and_survives_infinite_loops():
    from app.harness import mutation_test

    broken = mutation_test("def f():\n    return 1\n", "def test_f():\n    assert f() == 2\n")
    assert broken["available"] is False and "does not pass" in broken["error"]
    # Negating the loop condition would spin forever; the per-mutant timer counts it as killed
    loop = mutation_test(
        "def count(n):\n    i = 0\n    while i < n:\n        i += 1\n    return i\n",
        "def test_count():\n    assert count(3) == 3\n",
    )
    assert loop["available"] and loop["killed"] >= 1


def test_merge_tests_never_shadows_an_existing_test():
    from app.test_agent import merge_tests

    merged = merge_tests(
        "def test_a():\n    assert 1\n",
        "def test_a():\n    assert 2\n\ndef test_b():\n    assert 3\n",
    )
    assert merged.count("def test_a(") == 1 and "def test_a_strict(" in merged and "def test_b(" in merged
    compile(merged, "<tests>", "exec")


def test_error_signature_finds_the_exception_inside_harness_feedback():
    feedback = (
        "Exit code: 1\nTests passed: 4/7\n"
        "- test_fetch_status_success failed: urllib.error.URLError: <urlopen error [Errno -3] Temporary failure>"
    )
    assert error_signature(feedback).startswith("URLError: <urlopen error [Errno -N]")
    # Still stable for a plain traceback, and for text with no exception at all
    assert error_signature("Traceback...\nKeyError: 'id'") == "KeyError: 'id'"
    assert error_signature("Tests passed: 0/3") == "Tests passed: N/N"


def test_the_same_failure_twice_updates_one_memory_instead_of_adding_another():
    from app.memory import store_failure

    existing = {"kind": "failure", "task": "t", "workspace": "default", "uses": 3, "pinned": True, "seen": 1}
    coll = MagicMock()
    coll.count.return_value = 1
    coll.query.return_value = {"ids": [["mem-1"]], "distances": [[0.01]], "metadatas": [[existing]]}

    assert store_failure("t", "code v2", "ValueError: boom", collection=coll) == "mem-1"
    coll.add.assert_not_called()
    updated = coll.update.call_args.kwargs["metadatas"][0]
    assert updated["seen"] == 2 and updated["uses"] == 3 and updated["pinned"] is True
    assert updated["code"] == "code v2"          # the newest attempt replaces the old one

    # A different failure (low similarity) is a new memory
    coll.query.return_value = {"ids": [["mem-1"]], "distances": [[0.4]], "metadatas": [[existing]]}
    assert store_failure("other", "c", "KeyError: x", collection=coll) != "mem-1"
    coll.add.assert_called_once()
