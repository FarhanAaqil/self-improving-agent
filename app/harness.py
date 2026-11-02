"""Verification harness executed inside the sandbox.

The solution and its spec tests are embedded as string literals in a small driver
script. The driver runs the solution, calls every `test_*` function, measures line
coverage of the solution with sys.settrace, and prints one JSON report line tagged
with a per-run nonce so the solution cannot easily forge a passing result.
Only the standard library is used, so the stock python:3.11-slim image is enough.
"""

import json
import secrets
from dataclasses import dataclass, field

from app.config import SANDBOX_TIMEOUT
from app.sandbox import run_code

_DRIVER = r'''
import json as _json
import sys as _sys
import traceback as _tb

_SOLUTION = {solution!r}
_TESTS = {tests!r}
_MARKER = {marker!r}

_report = {{"solution_error": None, "tests_error": None, "total": 0, "passed": 0,
           "failures": [], "coverage": None}}
_hits = set()


def _tracer(frame, event, arg):
    if frame.f_code.co_filename == "<solution>":
        _hits.add(frame.f_lineno)
        return _tracer
    return None


def _executable(code):
    lines, stack = set(), [code]
    while stack:
        c = stack.pop()
        lines.update(n for _, _, n in c.co_lines() if n)
        stack.extend(k for k in c.co_consts if hasattr(k, "co_lines"))
    return lines


def _short(exc):
    text = "".join(_tb.format_exception_only(type(exc), exc)).strip()
    return text[:400]


def _finish(ok):
    _sys.stdout.flush()
    print("\n" + _MARKER + _json.dumps(_report), flush=True)
    _sys.exit(0 if ok else 1)


_ns = {{"__name__": "__main__"}}
try:
    _code = compile(_SOLUTION, "<solution>", "exec")
except SyntaxError as e:
    _tb.print_exc()
    _report["solution_error"] = _short(e)
    _finish(False)

_trace = bool(_TESTS)
if _trace:
    _sys.settrace(_tracer)
try:
    exec(_code, _ns)
except SystemExit as e:
    if e.code not in (None, 0):
        _report["solution_error"] = "SystemExit: " + str(e.code)
except BaseException as e:
    _tb.print_exc()
    _report["solution_error"] = _short(e)
finally:
    _sys.settrace(None)

if _report["solution_error"]:
    _finish(False)

if _TESTS:
    try:
        exec(compile(_TESTS, "<tests>", "exec"), _ns)
    except BaseException as e:
        _report["tests_error"] = _short(e)
        _finish(False)

    _tests = sorted((n, f) for n, f in list(_ns.items()) if n.startswith("test_") and callable(f))
    _report["total"] = len(_tests)
    for _name, _fn in _tests:
        _sys.settrace(_tracer)
        try:
            _fn()
            _report["passed"] += 1
        except BaseException as e:
            _report["failures"].append({{"test": _name, "error": _short(e)}})
        finally:
            _sys.settrace(None)

    _lines = _executable(_code)
    if _lines:
        _report["coverage"] = round(len(_hits & _lines) / len(_lines), 3)
    _finish(_report["total"] > 0 and _report["passed"] == _report["total"])

_finish(True)
'''


@dataclass
class Verification:
    success: bool
    output: str | None
    error: str | None
    exit_code: int | None
    latency_ms: int
    sandboxed: bool
    total: int = 0
    passed: int = 0
    coverage: float | None = None
    failures: list[dict] = field(default_factory=list)
    solution_error: str | None = None
    tests_error: str | None = None

    @property
    def report(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "coverage": self.coverage,
            "failures": self.failures,
            "solution_error": self.solution_error,
            "tests_error": self.tests_error,
        }

    def feedback(self) -> str:
        """Plain-text failure summary handed to the repair prompt."""
        parts = [f"Exit code: {self.exit_code}"]
        if self.solution_error:
            parts.append(f"The code itself crashed: {self.solution_error}")
        if self.tests_error:
            parts.append(f"The tests could not be loaded: {self.tests_error}")
        if self.total:
            parts.append(f"Tests passed: {self.passed}/{self.total}")
            for failure in self.failures[:6]:
                parts.append(f"- {failure['test']} failed: {failure['error']}")
        if self.error:
            tail = "\n".join(self.error.strip().splitlines()[-15:])
            parts.append(f"stderr (last lines):\n{tail}")
        return "\n".join(parts)


def build_driver(solution: str, tests: str | None, marker: str) -> str:
    return _DRIVER.format(solution=solution, tests=tests or "", marker=marker)


def verify(solution: str, tests: str | None = None, timeout: int = SANDBOX_TIMEOUT) -> Verification:
    """Run the solution plus spec tests in the sandbox and parse the harness report."""
    marker = f"__AGENT_REPORT_{secrets.token_hex(8)}__"
    raw = run_code(build_driver(solution, tests, marker), timeout=timeout)

    stdout = raw.get("output") or ""
    report: dict = {}
    if marker in stdout:
        visible, _, tail = stdout.rpartition(marker)
        try:
            report = json.loads(tail.strip().splitlines()[0])
        except (ValueError, IndexError):
            report = {}
        stdout = visible.rstrip()

    total = int(report.get("total") or 0)
    passed = int(report.get("passed") or 0)
    tests_ok = (total > 0 and passed == total) if tests else True
    clean_exit = raw.get("exit_code") == 0 and bool(report)

    return Verification(
        success=bool(raw.get("success")) and clean_exit and tests_ok,
        output=stdout or None,
        error=raw.get("error") or None,
        exit_code=raw.get("exit_code"),
        latency_ms=int(raw.get("latency_ms") or 0),
        sandboxed=bool(raw.get("sandboxed")),
        total=total,
        passed=passed,
        coverage=report.get("coverage"),
        failures=report.get("failures") or [],
        solution_error=report.get("solution_error"),
        tests_error=report.get("tests_error"),
    )
