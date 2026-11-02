"""Write the latest official, sandboxed benchmark result into README.md.

The table lives between <!-- BENCHMARK_TABLE_START --> and <!-- BENCHMARK_TABLE_END -->.
Only results that ran in the Docker sandbox on the official HumanEval tests are used.
"""

import argparse
import glob
import json
from pathlib import Path

START_MARKER = "<!-- BENCHMARK_TABLE_START -->"
END_MARKER = "<!-- BENCHMARK_TABLE_END -->"


def find_latest(results_dir: Path) -> dict | None:
    candidates = []
    for path in glob.glob(str(results_dir / "*.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("suite") == "official" and data.get("sandboxed"):
            candidates.append(data)
    return max(candidates, key=lambda d: d.get("run_at", ""), default=None)


def format_table(data: dict) -> str:
    agent, base = data["agent"], data["baseline"]
    k = agent["k"]
    return "\n".join([
        f"Official HumanEval, {data['total_problems']} problems, `{data['model']}`, "
        f"run {data['date']} in the Docker sandbox. Brackets show the 95% confidence interval.",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Baseline pass@1 (single shot, no feedback) | {base['pass_at_1']:.1f}% [{base['ci95'][0]}–{base['ci95'][1]}] |",
        f"| Agent pass@1 (first attempt) | {agent['pass_at_1']:.1f}% |",
        f"| Agent solve@{k} (with repair) | {agent['solve_at_k']:.1f}% [{agent['ci95'][0]}–{agent['ci95'][1]}] |",
        f"| Gain from repair | {data['repair_gain_pct']:+.1f} pts |",
        f"| Average attempts | {agent['avg_attempts']:.2f} |",
    ])


def update_readme(readme: Path, table: str) -> bool:
    text = readme.read_text(encoding="utf-8")
    if START_MARKER not in text or END_MARKER not in text:
        print("Benchmark markers not found in README.")
        return False
    head, rest = text.split(START_MARKER, 1)
    _, tail = rest.split(END_MARKER, 1)
    new = f"{head}{START_MARKER}\n{table}\n{END_MARKER}{tail}"
    if new == text:
        return False
    readme.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--readme-path", type=Path, default=Path("README.md"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = find_latest(args.results_dir)
    if not data:
        print("No official sandboxed results found; README left unchanged.")
        return
    table = format_table(data)
    if args.dry_run:
        print(table)
        return
    print("README updated." if update_readme(args.readme_path, table) else "README already current.")


if __name__ == "__main__":
    main()
