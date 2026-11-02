import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.config import DB_PATH


@contextmanager
def get_connection(db_path: str = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, and always close it."""
    # Ensure parent directory exists before SQLite creates the file
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        # WAL mode prevents database locks between readers and concurrent attempt writers.
        # Foreign keys pragma must be turned on explicitly per connection in SQLite.
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        with conn:
            yield conn
    finally:
        conn.close()


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

        CREATE TABLE IF NOT EXISTS run_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            payload TEXT,
            created_at TIMESTAMP NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_run ON run_events(run_id, event_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_run_id ON attempts(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_attempts_timestamp ON attempts(timestamp DESC);
        """)

        _add_missing_columns(conn, "attempts", ATTEMPT_COLUMNS)
        _add_missing_columns(conn, "runs", RUN_COLUMNS)


# Columns added after the first release. New databases and old ones converge on the same shape.
ATTEMPT_COLUMNS = {
    "critique_confidence": "REAL",
    "critique_reasoning": "TEXT",
    "generated_tests": "TEXT",
    "performance_notes": "TEXT",
    "security_audit": "TEXT",
    "quality_overall_score": "REAL",
    "quality_report_json": "TEXT",
    "tests_passed": "INTEGER",
    "tests_total": "INTEGER",
    "coverage": "REAL",
    "test_report_json": "TEXT",
    "diagnosis_json": "TEXT",
    "sandboxed": "BOOLEAN",
}

RUN_COLUMNS = {
    "model_name": "TEXT",
    "memories_json": "TEXT",
    "spec_tests": "TEXT",
    "final_code": "TEXT",
    "docs_applied": "BOOLEAN",
    "prompt_tokens": "INTEGER",
    "completion_tokens": "INTEGER",
    "finished_at": "TIMESTAMP",
    "workspace": "TEXT DEFAULT 'default'",
    "group_id": "TEXT",
    "share_token": "TEXT",
}


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, decl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl};")


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


_RUN_UPDATABLE = {"final_status", "total_attempts"} | set(RUN_COLUMNS)


def update_run(run_id: str, db_path: str = DB_PATH, **fields: Any) -> None:
    """Update any whitelisted run columns. Unknown keys raise instead of silently vanishing."""
    unknown = set(fields) - _RUN_UPDATABLE
    if unknown:
        raise ValueError(f"Unknown run fields: {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with get_connection(db_path) as conn:
        conn.execute(f"UPDATE runs SET {assignments} WHERE run_id = ?", [*fields.values(), run_id])


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
    **extra: Any,
) -> int:
    unknown = set(extra) - set(ATTEMPT_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown attempt fields: {sorted(unknown)}")
    row = {
        "run_id": run_id,
        "attempt_number": attempt_number,
        "generated_code": generated_code,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "success": int(success),
        "latency_ms": latency_ms,
        "tokens_used": tokens_used,
        "model_name": model_name,
        "critique_confidence": critique_confidence,
        "critique_reasoning": critique_reasoning,
        "generated_tests": generated_tests,
        "performance_notes": performance_notes,
        "security_audit": security_audit,
        "quality_overall_score": quality_overall_score,
        "quality_report_json": quality_report_json,
        "timestamp": (timestamp or datetime.now()).isoformat(),
        **extra,
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" * len(row))
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            f"INSERT INTO attempts ({columns}) VALUES ({placeholders})", list(row.values())
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


# ── Run summaries & events ───────────────────────────────────

_SUMMARY_SQL = """
    SELECT r.run_id, r.task_description, r.created_at, r.final_status, r.total_attempts,
           r.model_name, r.prompt_tokens, r.completion_tokens, r.finished_at, r.group_id,
           (SELECT MIN(a.attempt_number) FROM attempts a
             WHERE a.run_id = r.run_id AND a.success = 1) AS passed_on_attempt,
           (SELECT MAX(a.quality_overall_score) FROM attempts a
             WHERE a.run_id = r.run_id) AS quality_score,
           (SELECT COALESCE(SUM(a.latency_ms), 0) FROM attempts a
             WHERE a.run_id = r.run_id) AS total_latency_ms
    FROM runs r
"""

STATUS_GROUPS = {
    "success": ("success",),
    "failed": ("failed", "max_retries_exceeded", "early_stopped"),
    "early_stopped": ("early_stopped",),
    "running": ("running", "queued"),
}


def list_run_summaries(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: str | None = None,
    workspace: str | None = None,
    db_path: str = DB_PATH,
) -> dict[str, Any]:
    """Lightweight, server-side paginated run list (no generated code in the payload)."""
    where, params = [], []
    if q:
        where.append("(r.run_id LIKE ? OR r.task_description LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if status and status in STATUS_GROUPS:
        group = STATUS_GROUPS[status]
        where.append(f"r.final_status IN ({','.join('?' * len(group))})")
        params += list(group)
    if workspace:
        where.append("COALESCE(r.workspace, 'default') = ?")
        params.append(workspace)
    clause = f" WHERE {' AND '.join(where)}" if where else ""

    with get_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM runs r{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"{_SUMMARY_SQL}{clause} ORDER BY r.created_at DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
        counts = {
            row["final_status"]: row["n"]
            for row in conn.execute(
                f"SELECT final_status, COUNT(*) AS n FROM runs r{clause} GROUP BY final_status", params
            )
        }
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": counts,
    }


def add_event(run_id: str, event_type: str, payload: dict | None = None, db_path: str = DB_PATH) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO run_events (run_id, type, payload, created_at) VALUES (?, ?, ?, ?)",
            (run_id, event_type, json.dumps(payload or {}, default=str), datetime.now().isoformat()),
        )
        return cursor.lastrowid


def get_events(run_id: str, after_id: int = 0, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT event_id, type, payload, created_at FROM run_events "
            "WHERE run_id = ? AND event_id > ? ORDER BY event_id ASC",
            (run_id, after_id),
        ).fetchall()
    return [
        {**dict(r), "payload": json.loads(r["payload"]) if r["payload"] else {}}
        for r in rows
    ]


def run_stats_by_day(days: int = 60, workspace: str | None = None, db_path: str = DB_PATH) -> list[dict]:
    """Per-day counts used by the improvement-over-time chart."""
    params: list[Any] = [f"-{int(days)} days"]
    ws = ""
    if workspace:
        ws = " AND COALESCE(r.workspace, 'default') = ?"
        params.append(workspace)
    sql = f"""
        SELECT substr(r.created_at, 1, 10) AS day,
               COUNT(*) AS runs,
               SUM(CASE WHEN r.final_status = 'success' THEN 1 ELSE 0 END) AS solved,
               SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts a WHERE a.run_id = r.run_id
                        AND a.attempt_number = 1 AND a.success = 1) THEN 1 ELSE 0 END) AS first_try,
               SUM(CASE WHEN r.memories_json IS NOT NULL AND r.memories_json != '[]'
                        THEN 1 ELSE 0 END) AS used_memory,
               AVG(r.total_attempts) AS avg_attempts
        FROM runs r
        WHERE r.created_at >= date('now', ?){ws}
        GROUP BY day ORDER BY day ASC
    """
    with get_connection(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ── Workspaces, usage, sharing, compare groups ───────────────

def tokens_today(workspace: str | None = None, db_path: str = DB_PATH) -> int:
    """Tokens spent by runs created today (UTC date of created_at), optionally per workspace."""
    sql = (
        "SELECT COALESCE(SUM(COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0)), 0) "
        "FROM runs WHERE substr(created_at, 1, 10) = ?"
    )
    params: list[Any] = [datetime.now().date().isoformat()]
    if workspace:
        sql += " AND COALESCE(workspace, 'default') = ?"
        params.append(workspace)
    with get_connection(db_path) as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def run_workspace(run_id: str, db_path: str = DB_PATH) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COALESCE(workspace, 'default') FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return row[0] if row else None


def get_run_by_share_token(token: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT run_id FROM runs WHERE share_token = ?", (token,)).fetchone()
    return get_run_with_attempts(row[0], db_path=db_path) if row else None


def list_group_runs(group_id: str, workspace: str | None = None, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    params: list[Any] = [group_id]
    ws = ""
    if workspace:
        ws = " AND COALESCE(r.workspace, 'default') = ?"
        params.append(workspace)
    with get_connection(db_path) as conn:
        rows = conn.execute(f"{_SUMMARY_SQL} WHERE r.group_id = ?{ws} ORDER BY r.model_name", params).fetchall()
    return [dict(r) for r in rows]


def memory_effect(workspace: str | None = None, db_path: str = DB_PATH) -> dict[str, Any]:
    """First-try success with and without recalled memory: does remembering actually help?"""
    params: list[Any] = []
    ws = ""
    if workspace:
        ws = " AND COALESCE(r.workspace, 'default') = ?"
        params.append(workspace)
    sql = f"""
        SELECT
          CASE WHEN r.memories_json IS NOT NULL AND r.memories_json != '[]' THEN 'with' ELSE 'without' END AS bucket,
          COUNT(*) AS runs,
          SUM(CASE WHEN r.final_status = 'success' THEN 1 ELSE 0 END) AS solved,
          SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts a WHERE a.run_id = r.run_id
                   AND a.attempt_number = 1 AND a.success = 1) THEN 1 ELSE 0 END) AS first_try,
          AVG(r.total_attempts) AS avg_attempts
        FROM runs r
        WHERE r.final_status IN ('success', 'max_retries_exceeded', 'early_stopped', 'failed'){ws}
        GROUP BY bucket
    """
    with get_connection(db_path) as conn:
        rows = {r["bucket"]: dict(r) for r in conn.execute(sql, params).fetchall()}
    empty = {"runs": 0, "solved": 0, "first_try": 0, "avg_attempts": None}
    return {"with_memory": rows.get("with", empty), "without_memory": rows.get("without", empty)}
