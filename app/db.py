import os
import sqlite3
from datetime import datetime
from typing import Any

from app.config import DB_PATH


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    # Ensure parent directory exists before SQLite creates the file
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # WAL mode prevents database locks between readers and concurrent attempt writers.
    # Foreign keys pragma must be turned on explicitly per connection in SQLite.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            task_description TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            final_status TEXT NOT NULL,
            total_attempts INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL,
            generated_code TEXT NOT NULL,
            stdout TEXT,
            stderr TEXT,
            exit_code INTEGER,
            success BOOLEAN NOT NULL,
            latency_ms INTEGER,
            tokens_used INTEGER,
            model_name TEXT,
            critique_confidence REAL,
            critique_reasoning TEXT,
            generated_tests TEXT,
            performance_notes TEXT,
            security_audit TEXT,
            quality_overall_score REAL,
            quality_report_json TEXT,
            timestamp TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eval_runs (
            eval_id TEXT PRIMARY KEY,
            benchmark_name TEXT NOT NULL,
            pass_at_1 REAL,
            pass_at_5 REAL,
            avg_attempts REAL,
            avg_latency_ms REAL,
            total_problems INTEGER,
            run_at TIMESTAMP NOT NULL,
            raw_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_attempts_run_id ON attempts(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_attempts_timestamp ON attempts(timestamp DESC);
        """)

        # Auto-migrate table columns if upgrading existing database
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        if "critique_confidence" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN critique_confidence REAL;")
        if "critique_reasoning" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN critique_reasoning TEXT;")
        if "generated_tests" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN generated_tests TEXT;")
        if "performance_notes" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN performance_notes TEXT;")
        if "security_audit" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN security_audit TEXT;")
        if "quality_overall_score" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN quality_overall_score REAL;")
        if "quality_report_json" not in existing_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN quality_report_json TEXT;")


def insert_run(
    run_id: str,
    task_description: str,
    created_at: datetime | None = None,
    final_status: str = "running",
    total_attempts: int = 0,
    db_path: str = DB_PATH,
) -> None:
    now = (created_at or datetime.now()).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (run_id, task_description, created_at, final_status, total_attempts)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                final_status = excluded.final_status,
                total_attempts = excluded.total_attempts
            """,
            (run_id, task_description, now, final_status, total_attempts),
        )


def update_run_status(
    run_id: str,
    final_status: str,
    total_attempts: int | None = None,
    db_path: str = DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        if total_attempts is not None:
            conn.execute(
                "UPDATE runs SET final_status = ?, total_attempts = ? WHERE run_id = ?",
                (final_status, total_attempts, run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET final_status = ? WHERE run_id = ?",
                (final_status, run_id),
            )


def insert_attempt(
    run_id: str,
    attempt_number: int,
    generated_code: str,
    stdout: str | None = None,
    stderr: str | None = None,
    exit_code: int | None = 0,
    success: bool = True,
    latency_ms: int | None = 0,
    tokens_used: int | None = None,
    model_name: str | None = None,
    critique_confidence: float | None = None,
    critique_reasoning: str | None = None,
    generated_tests: str | None = None,
    performance_notes: str | None = None,
    security_audit: str | None = None,
    quality_overall_score: float | None = None,
    quality_report_json: str | None = None,
    timestamp: datetime | None = None,
    db_path: str = DB_PATH,
) -> int:
    now = (timestamp or datetime.now()).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO attempts (
                run_id, attempt_number, generated_code, stdout, stderr,
                exit_code, success, latency_ms, tokens_used, model_name,
                critique_confidence, critique_reasoning, generated_tests, performance_notes,
                security_audit, quality_overall_score, quality_report_json, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, attempt_number, generated_code, stdout, stderr,
                exit_code, int(success), latency_ms, tokens_used, model_name,
                critique_confidence, critique_reasoning, generated_tests, performance_notes,
                security_audit, quality_overall_score, quality_report_json, now,
            ),
        )
        return cursor.lastrowid


def update_attempt_review(
    attempt_id: int,
    critique_confidence: float | None = None,
    critique_reasoning: str | None = None,
    generated_tests: str | None = None,
    performance_notes: str | None = None,
    security_audit: str | None = None,
    quality_overall_score: float | None = None,
    quality_report_json: str | None = None,
    generated_code: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    updates: list[str] = []
    params: list[Any] = []

    if critique_confidence is not None:
        updates.append("critique_confidence = ?")
        params.append(critique_confidence)
    if critique_reasoning is not None:
        updates.append("critique_reasoning = ?")
        params.append(critique_reasoning)
    if generated_tests is not None:
        updates.append("generated_tests = ?")
        params.append(generated_tests)
    if performance_notes is not None:
        updates.append("performance_notes = ?")
        params.append(performance_notes)
    if security_audit is not None:
        updates.append("security_audit = ?")
        params.append(security_audit)
    if quality_overall_score is not None:
        updates.append("quality_overall_score = ?")
        params.append(quality_overall_score)
    if quality_report_json is not None:
        updates.append("quality_report_json = ?")
        params.append(quality_report_json)
    if generated_code is not None:
        updates.append("generated_code = ?")
        params.append(generated_code)

    if not updates:
        return

    params.append(attempt_id)
    sql = f"UPDATE attempts SET {', '.join(updates)} WHERE attempt_id = ?"
    with get_connection(db_path) as conn:
        conn.execute(sql, params)


def get_run(run_id: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def get_run_with_attempts(run_id: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    run = get_run(run_id, db_path=db_path)
    if not run:
        return None

    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM attempts WHERE run_id = ? ORDER BY attempt_number ASC",
            (run_id,),
        ).fetchall()
        run["attempts"] = [dict(r) for r in rows]
        return run


def list_runs(limit: int = 50, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        run_rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        runs = [dict(r) for r in run_rows]

        if not runs:
            return runs

        run_ids = [r["run_id"] for r in runs]
        placeholders = ",".join("?" * len(run_ids))
        attempt_rows = conn.execute(
            f"SELECT * FROM attempts WHERE run_id IN ({placeholders}) ORDER BY run_id, attempt_number ASC",
            run_ids,
        ).fetchall()

        # Group attempts by run_id
        attempts_by_run: dict[str, list] = {r["run_id"]: [] for r in runs}
        for row in attempt_rows:
            attempts_by_run[row["run_id"]].append(dict(row))

        for run in runs:
            run["attempts"] = attempts_by_run.get(run["run_id"], [])

        return runs


def insert_eval_run(
    eval_id: str,
    benchmark_name: str,
    pass_at_1: float | None = None,
    pass_at_5: float | None = None,
    avg_attempts: float | None = None,
    avg_latency_ms: float | None = None,
    total_problems: int | None = None,
    run_at: datetime | None = None,
    raw_json: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    now = (run_at or datetime.now()).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO eval_runs (
                eval_id, benchmark_name, pass_at_1, pass_at_5,
                avg_attempts, avg_latency_ms, total_problems, run_at, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id, benchmark_name, pass_at_1, pass_at_5,
                avg_attempts, avg_latency_ms, total_problems, now, raw_json,
            ),
        )


def get_latest_eval_run(
    benchmark_name: str | None = None,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        if benchmark_name:
            row = conn.execute(
                "SELECT * FROM eval_runs WHERE benchmark_name = ? ORDER BY run_at DESC LIMIT 1",
                (benchmark_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM eval_runs ORDER BY run_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
