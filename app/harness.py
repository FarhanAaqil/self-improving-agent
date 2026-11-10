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


# ── Mutation testing: how much do the spec tests actually pin down? ──────────

_MUTATION_DRIVER = r'''
import ast as _ast
import io as _io
import json as _json
import signal as _signal
import sys as _sys
import time as _time

_SOLUTION = {solution!r}
_TESTS = {tests!r}
_MARKER = {marker!r}
_MAX = {max_mutants}
_BUDGET = {budget}
_PER = {per_mutant}

_CMP = {{_ast.Lt: _ast.LtE, _ast.LtE: _ast.Lt, _ast.Gt: _ast.GtE, _ast.GtE: _ast.Gt,
        _ast.Eq: _ast.NotEq, _ast.NotEq: _ast.Eq}}
_BIN = {{_ast.Add: _ast.Sub, _ast.Sub: _ast.Add, _ast.Mult: _ast.Add, _ast.FloorDiv: _ast.Mult,
        _ast.Div: _ast.Mult, _ast.Mod: _ast.Mult}}
_SYM = {{_ast.Lt: "<", _ast.LtE: "<=", _ast.Gt: ">", _ast.GtE: ">=", _ast.Eq: "==", _ast.NotEq: "!=",
        _ast.Add: "+", _ast.Sub: "-", _ast.Mult: "*", _ast.FloorDiv: "//", _ast.Div: "/", _ast.Mod: "%"}}
_report = {{"total": 0, "killed": 0, "survivors": [], "error": None}}
_lines = _SOLUTION.splitlines()


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def _finish():
    _sys.stdout = _sys.__stdout__
    print("\n" + _MARKER + _json.dumps(_report), flush=True)
    _sys.exit(0)


def _sites(tree):
    """(index in ast.walk order, kind, line, description) for every mutable spot inside a def/class."""
    inside = set()
    for top in tree.body:
        if isinstance(top, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            inside.update(id(n) for n in _ast.walk(top))
    found = []
    for index, node in enumerate(_ast.walk(tree)):
        if id(node) not in inside:
            continue
        line = getattr(node, "lineno", 0)
        if isinstance(node, _ast.Compare) and type(node.ops[0]) in _CMP:
            op = type(node.ops[0])
            found.append((index, "cmp", line, "`%s` became `%s`" % (_SYM[op], _SYM[_CMP[op]])))
        elif isinstance(node, _ast.BinOp) and type(node.op) in _BIN:
            op = type(node.op)
            found.append((index, "bin", line, "`%s` became `%s`" % (_SYM[op], _SYM[_BIN[op]])))
        elif isinstance(node, _ast.BoolOp):
            swap = ("and", "or") if isinstance(node.op, _ast.And) else ("or", "and")
            found.append((index, "bool", line, "`%s` became `%s`" % swap))
        elif isinstance(node, _ast.Constant) and isinstance(node.value, bool):
            found.append((index, "flag", line, "`%s` became `%s`" % (node.value, not node.value)))
        elif isinstance(node, _ast.Constant) and type(node.value) is int:
            found.append((index, "int", line, "`%d` became `%d`" % (node.value, node.value + 1)))
        elif isinstance(node, (_ast.If, _ast.While)):
            found.append((index, "negate", line, "the condition was negated"))
    return found


def _mutant(index, kind):
    tree = _ast.parse(_SOLUTION)
    node = list(_ast.walk(tree))[index]
    if kind == "cmp":
        node.ops[0] = _CMP[type(node.ops[0])]()
    elif kind == "bin":
        node.op = _BIN[type(node.op)]()
    elif kind == "bool":
        node.op = _ast.Or() if isinstance(node.op, _ast.And) else _ast.And()
    elif kind == "flag":
        node.value = not node.value
    elif kind == "int":
        node.value = node.value + 1
    elif kind == "negate":
        node.test = _ast.UnaryOp(op=_ast.Not(), operand=node.test)
    _ast.fix_missing_locations(tree)
    return compile(tree, "<mutant>", "exec")


def _passes(code, tests_code):
    namespace = {{"__name__": "__main__"}}
    try:
        _signal.setitimer(_signal.ITIMER_REAL, _PER)
        exec(code, namespace)
        exec(tests_code, namespace)
        tests = sorted((n, f) for n, f in list(namespace.items()) if n.startswith("test_") and callable(f))
        for _name, fn in tests:
            fn()
        return bool(tests)
    except BaseException:
        return False
    finally:
        _signal.setitimer(_signal.ITIMER_REAL, 0)


_signal.signal(_signal.SIGALRM, _alarm)
_sys.stdout = _io.StringIO()
try:
    _tree = _ast.parse(_SOLUTION)
    _tests_code = compile(_TESTS, "<tests>", "exec")
except SyntaxError as e:
    _report["error"] = "syntax error: " + str(e)
    _finish()

if not _passes(compile(_tree, "<solution>", "exec"), _tests_code):
    _report["error"] = "the unmodified solution does not pass its tests"
    _finish()

_all = _sites(_tree)
if len(_all) > _MAX:  # evenly spaced, deterministic sample
    _all = [_all[int(i * len(_all) / _MAX)] for i in range(_MAX)]

_start = _time.monotonic()
for _index, _kind, _line, _what in _all:
    if _time.monotonic() - _start > _BUDGET:
        break
    try:
        _code = _mutant(_index, _kind)
    except Exception:
        continue
    _report["total"] += 1
    if _passes(_code, _tests_code):
        _source = _lines[_line - 1].strip() if 0 < _line <= len(_lines) else ""
        _report["survivors"].append({{"line": _line, "source": _source[:160], "change": _what}})
    else:
        _report["killed"] += 1

_finish()
'''


def mutation_test(
    solution: str,
    tests: str,
    max_mutants: int = 30,
    timeout: int = 30,
) -> dict:
    """
    Break the solution in small ways and count how many breaks the tests notice.
    Returns {available, total, killed, score, survivors, error}. A surviving mutant is a
    behaviour change no test caught, i.e. a spot the tests do not really pin down.
    """
    marker = f"__MUTATION_{secrets.token_hex(8)}__"
    driver = _MUTATION_DRIVER.format(
        solution=solution,
        tests=tests,
        marker=marker,
        max_mutants=max_mutants,
        budget=max(3, timeout - 10),
        per_mutant=2,
    )
    raw = run_code(driver, timeout=timeout)
    stdout = raw.get("output") or ""
    report: dict = {}
    if marker in stdout:
        try:
            report = json.loads(stdout.rpartition(marker)[2].strip().splitlines()[0])
        except (ValueError, IndexError):
            report = {}

    if not report or report.get("error"):
        return {
            "available": False, "total": 0, "killed": 0, "score": None, "survivors": [],
            "error": report.get("error") or (raw.get("error") or "mutation run produced no report")[:300],
        }
    total = int(report["total"])
    killed = int(report["killed"])
    return {
        "available": total > 0,
        "total": total,
        "killed": killed,
        "score": round(killed / total, 3) if total else None,
        "survivors": report.get("survivors", [])[:12],
        "error": None,
    }
