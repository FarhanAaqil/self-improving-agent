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
                critique_confidence, generated_tests, performance_notes,
                security_audit, quality_overall_score, quality_report_json, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, attempt_number, generated_code, stdout, stderr,
                exit_code, int(success), latency_ms, tokens_used, model_name,
                critique_confidence, generated_tests, performance_notes,
                security_audit, quality_overall_score, quality_report_json, now,
            ),
        )
        return cursor.lastrowid


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
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


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
