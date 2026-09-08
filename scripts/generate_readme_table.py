"""Generate README benchmark table from evaluation result JSONs.

Reads the latest or specified evaluation JSON file in results/ and updates the
markdown table in README.md between the benchmark markers:
<!-- BENCHMARK_TABLE_START -->
<!-- BENCHMARK_TABLE_END -->
"""

import argparse
import json
import sys
from pathlib import Path

START_MARKER = "<!-- BENCHMARK_TABLE_START -->"
END_MARKER = "<!-- BENCHMARK_TABLE_END -->"


def find_latest_results_file(results_dir: Path) -> Path | None:
    """Find the most recent humaneval results json file in results_dir."""
    files = sorted(results_dir.glob("humaneval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def format_table(data: dict) -> str:
    """Format evaluation metrics into a Markdown table."""
    pass_at_1 = data.get("pass_at_1", 0.0)
    pass_at_5 = data.get("pass_at_5", 0.0)
    avg_attempts = data.get("avg_attempts", 1.0)
    avg_latency = data.get("avg_latency_ms", 0.0)

    rows = [
        "| Metric | Self-Improving Agent | Baseline (Zero-Shot) |",
        "|---|---|---|",
        f"| pass@1 | {pass_at_1:.1f}% | 68.0% (single-pass) |",
        f"| pass@5 | {pass_at_5:.1f}% | 68.0% (no repair) |",
        f"| Avg repair attempts | {avg_attempts:.2f} | 1.0 (no repair) |",
        f"| Avg latency | {avg_latency:.1f} ms | ~50 ms |",
    ]
    return "\n".join(rows)


def update_readme(readme_path: Path, table_md: str) -> bool:
    """Replace content between markers in readme_path with table_md."""
    if not readme_path.exists():
        print(f"Error: {readme_path} not found.", file=sys.stderr)
        return False

    content = readme_path.read_text(encoding="utf-8")
    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)

    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        print(f"Error: Markers '{START_MARKER}' and '{END_MARKER}' not found in {readme_path}.", file=sys.stderr)
        return False

    new_section = f"{START_MARKER}\n{table_md}\n{END_MARKER}"
    updated_content = content[:start_idx] + new_section + content[end_idx + len(END_MARKER):]

    readme_path.write_text(updated_content, encoding="utf-8")
    print(f"Successfully updated {readme_path} with benchmark metrics.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark table for README from eval results.")
    parser.add_argument("--results-file", type=Path, default=None, help="Path to evaluation JSON result file.")
    parser.add_argument("--readme-path", type=Path, default=Path("README.md"), help="Path to README.md.")
    parser.add_argument("--update", action="store_true", default=True, help="Update README.md in-place.")
    parser.add_argument("--dry-run", action="store_true", help="Print table without updating README.")

    args = parser.parse_args()

    results_file = args.results_file
    if not results_file:
        results_dir = Path("results")
        results_file = find_latest_results_file(results_dir)
        if not results_file:
            print(f"No humaneval_*.json found in {results_dir}.", file=sys.stderr)
            sys.exit(1)

    print(f"Reading evaluation data from: {results_file}")
    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)

    table_md = format_table(data)
    print("\nGenerated Markdown Table:\n")
    print(table_md)
    print()

    if not args.dry_run and args.update:
        success = update_readme(args.readme_path, table_md)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
