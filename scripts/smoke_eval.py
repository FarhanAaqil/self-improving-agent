"""Smoke evaluation for CI: a few official HumanEval problems through the sandbox.

Skips cleanly when GROQ_API_KEY is missing (forks, PRs from contributors).
Fails the build when the agent's solve rate drops more than --threshold-drop points
below the latest committed result for the same suite.
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.benchmark import run_benchmark  # noqa: E402


def latest_solve_rate(results_dir: Path) -> float | None:
    """solve@k from the most recent committed official result, by its recorded run time."""
    best: tuple[str, float] | None = None
    for path in glob.glob(str(results_dir / "humaneval_*.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("suite") != "official" or not data.get("sandboxed"):
            continue
        stamp = data.get("run_at", "")
        if best is None or stamp > best[0]:
            best = (stamp, float(data["agent"]["solve_at_k"]))
    return best[1] if best else None


def main() -> None:
    parser = argparse.ArgumentParser(description="CI smoke evaluation")
    parser.add_argument("--problems", type=int, default=8)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--threshold-drop", type=float, default=15.0)
    args = parser.parse_args()

    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or key == "mock-api-key":
        print("[smoke] GROQ_API_KEY not set; skipping.")
        return

    summary = run_benchmark(suite="humaneval", limit=args.problems, attempts=args.attempts)
    rate = summary["agent"]["solve_at_k"]
    print(f"[smoke] solve@{args.attempts}: {rate:.1f}%  baseline pass@1: {summary['baseline']['pass_at_1']:.1f}%")

    reference = latest_solve_rate(_ROOT / "results")
    if reference is None:
        print("[smoke] No committed official result yet; nothing to compare against.")
        return
    floor = max(0.0, reference - args.threshold_drop)
    if rate < floor:
        print(f"[smoke] Regression: {rate:.1f}% is below the {floor:.1f}% floor (reference {reference:.1f}%).")
        sys.exit(1)
    print(f"[smoke] OK against reference {reference:.1f}%.")


if __name__ == "__main__":
    main()
