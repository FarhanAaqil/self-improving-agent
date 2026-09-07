# One-off migration utility: imports legacy JSONL logs into SQLite.
# Safe to run multiple times without duplicating data.
import argparse
import json
import os
import sys
from datetime import datetime
import uuid

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db, insert_run, insert_attempt
from app.config import DB_PATH, LOG_DIR


def migrate(jsonl_path: str, db_path: str = DB_PATH) -> tuple[int, int]:
    if not os.path.exists(jsonl_path):
        print(f"Log file {jsonl_path} does not exist. Nothing to migrate.")
        return (0, 0)

    init_db(db_path)
    runs_created = 0
    attempts_migrated = 0
    run_cache = {}

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            task = entry.get("task", "legacy task")
            if task not in run_cache:
                run_id = f"migrated_{uuid.uuid4().hex[:8]}"
                created_at = None
                if entry.get("timestamp"):
                    try:
                        created_at = datetime.fromisoformat(entry["timestamp"])
                    except ValueError:
                        pass

                insert_run(
                    run_id=run_id,
                    task_description=task,
                    created_at=created_at,
                    final_status="success" if entry.get("success") else "failed",
                    db_path=db_path,
                )
                run_cache[task] = run_id
                runs_created += 1

            run_id = run_cache[task]
            insert_attempt(
                run_id=run_id,
                attempt_number=entry.get("attempt", 1),
                generated_code=entry.get("code", ""),
                stdout=entry.get("output"),
                stderr=entry.get("error"),
                exit_code=0 if entry.get("success") else 1,
                success=bool(entry.get("success")),
                db_path=db_path,
            )
            attempts_migrated += 1

    print(f"Migration complete: {attempts_migrated} attempts across {runs_created} runs migrated to {db_path}")
    return (runs_created, attempts_migrated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate legacy JSONL attempts to SQLite")
    parser.add_argument(
        "--file",
        default=os.path.join(LOG_DIR, "attempts.jsonl"),
        help="Path to attempts.jsonl file",
    )
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database")
    args = parser.parse_args()
    migrate(args.file, args.db)
