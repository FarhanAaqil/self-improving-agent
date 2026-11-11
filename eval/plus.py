"""HumanEval+ judge: far stricter hidden tests than the original HumanEval.

HumanEval+ (EvalPlus, Apache-2.0) ships ~750 extra inputs per problem instead of
expected outputs. The expected value for each input is whatever the canonical
solution returns, so the judge runs the reference and the candidate side by side
inside one sandbox execution and stops at the first disagreement.

Nothing about the hidden inputs ever reaches the agent: callers only learn
"passed" or a coarse failure kind (wrong value / exception type / timeout).
"""

import gzip
import json
import os
import secrets
from functools import lru_cache
from typing import Any

from app.sandbox import run_code

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "HumanEvalPlus.jsonl.gz")
JUDGE_TIMEOUT = int(os.getenv("JUDGE_TIMEOUT", "40"))
PER_INPUT_SECONDS = 3

_DRIVER = r'''
import copy as _copy
import io as _io
import json as _json
import math as _math
import signal as _signal
import sys as _sys

_REF = {reference!r}
_CAND = {candidate!r}
_ENTRY = {entry!r}
_INPUTS = _json.loads({inputs!r})
_ATOL = max(float({atol!r}), 1e-6)
_MARKER = {marker!r}
_TASK = {task!r}
_report = {{"total": len(_INPUTS), "passed": 0, "failure": None}}


def _finish():
    _sys.stdout = _sys.__stdout__
    print("\n" + _MARKER + _json.dumps(_report), flush=True)
    _sys.exit(0 if _report["failure"] is None else 1)


def _same(a, b):
    if a == b:
        return True
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        try:
            return _math.isclose(a, b, rel_tol=0.0, abs_tol=_ATOL)
        except (TypeError, OverflowError):
            return False
    if type(a) is type(b) and isinstance(a, (list, tuple)) and len(a) == len(b):
        return all(_same(x, y) for x, y in zip(a, b))
    return False


def _poly(xs, x):
    return sum(c * x ** i for i, c in enumerate(xs))


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


_signal.signal(_signal.SIGALRM, _alarm)
_ref_ns, _cand_ns = {{"__name__": "reference"}}, {{"__name__": "candidate"}}
_sys.stdout = _io.StringIO()
try:
    exec(compile(_REF, "<reference>", "exec"), _ref_ns)
except BaseException as e:
    _report["failure"] = {{"kind": "judge_error", "detail": type(e).__name__}}
    _finish()
try:
    _signal.alarm({load_seconds})
    exec(compile(_CAND, "<candidate>", "exec"), _cand_ns)
    _signal.alarm(0)
except BaseException as e:
    _signal.alarm(0)
    _report["failure"] = {{"kind": "load_error", "detail": type(e).__name__}}
    _finish()

_ref, _cand = _ref_ns.get(_ENTRY), _cand_ns.get(_ENTRY)
if not callable(_cand):
    _report["failure"] = {{"kind": "missing_function", "detail": _ENTRY}}
    _finish()

for _args in _INPUTS:
    try:
        _expected = _ref(*_copy.deepcopy(_args))
    except BaseException:
        _report["total"] -= 1  # input the reference itself rejects; not a fair test
        continue
    try:
        _signal.setitimer(_signal.ITIMER_REAL, {per_input})
        _got = _cand(*_copy.deepcopy(_args))
        _signal.setitimer(_signal.ITIMER_REAL, 0)
    except _Timeout:
        _report["failure"] = {{"kind": "timeout", "detail": ""}}
        break
    except BaseException as e:
        _signal.setitimer(_signal.ITIMER_REAL, 0)
        _report["failure"] = {{"kind": "exception", "detail": type(e).__name__}}
        break
    if _TASK == "HumanEval/32":
        _ok = isinstance(_got, (int, float)) and abs(_poly(_args[0], _got)) <= 1e-4
    else:
        _ok = _same(_expected, _got)
    if not _ok:
        _report["failure"] = {{"kind": "wrong_value", "detail": ""}}
        break
    _report["passed"] += 1

_finish()
'''


@lru_cache(maxsize=1)
def load_problems() -> list[dict[str, Any]]:
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [
        {
            "id": r["task_id"],
            "prompt": r["prompt"],
            "entry_point": r["entry_point"],
            "reference": r["prompt"] + r["canonical_solution"],
            "inputs": r["base_input"] + r["plus_input"],
            "atol": r["atol"],
        }
        for r in rows
    ]


def candidate_program(problem: dict, completion: str) -> str:
    # Prompt first so helpers it defines exist; a full function in the completion redefines the stub.
    return f"{problem['prompt']}\n    pass\n\n{completion}\n"


def judge(problem: dict, completion: str, timeout: int = JUDGE_TIMEOUT) -> dict:
    """Run the candidate against every hidden input. Returns passed / kind / counts / sandboxed."""
    marker = f"__JUDGE_{secrets.token_hex(8)}__"
    driver = _DRIVER.format(
        reference=problem["reference"],
        candidate=candidate_program(problem, completion),
        entry=problem["entry_point"],
        inputs=json.dumps(problem["inputs"]),
        atol=problem["atol"],
        marker=marker,
        task=problem["id"],
        load_seconds=5,
        per_input=PER_INPUT_SECONDS,
    )
    raw = run_code(driver, timeout=timeout)
    stdout = raw.get("output") or ""
    report: dict = {}
    if marker in stdout:
        try:
            report = json.loads(stdout.rpartition(marker)[2].strip().splitlines()[0])
        except (ValueError, IndexError):
            report = {}

    failure = report.get("failure")
    if not report:
        kind = "timeout" if "timed out" in (raw.get("error") or "") else "crashed"
        failure = {"kind": kind, "detail": ""}
    return {
        "passed": bool(report) and failure is None and raw.get("exit_code") == 0,
        "kind": None if failure is None else failure["kind"],
        "detail": "" if failure is None else failure.get("detail", ""),
        "inputs_total": report.get("total"),
        "inputs_passed": report.get("passed"),
        "sandboxed": bool(raw.get("sandboxed")),
        "latency_ms": int(raw.get("latency_ms") or 0),
    }


def safe_feedback(result: dict) -> str:
    """What the agent may learn about a hidden-test failure: the kind, never the inputs."""
    kind = result.get("kind")
    if kind == "wrong_value":
        return "Hidden tests failed: a returned value was wrong on at least one input. Re-read the spec and edge cases."
    if kind == "exception":
        return f"Hidden tests failed: the function raised {result.get('detail') or 'an exception'} on a valid input."
    if kind == "timeout":
        return "Hidden tests timed out: the solution is too slow or loops forever on some input."
    if kind in ("load_error", "missing_function"):
        return f"The code could not be loaded or does not define the required function ({result.get('detail')})."
    return "Hidden tests failed."
