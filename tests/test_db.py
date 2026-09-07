import os
import tempfile

import pytest

from app.db import (
    get_latest_eval_run,
    get_run,
    get_run_with_attempts,
    init_db,
    insert_attempt,
    insert_eval_run,
    insert_run,
    list_runs,
    update_run_status,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def test_runs_and_attempts_lifecycle(temp_db):
    run_id = "test-run-101"
    insert_run(run_id, "Write a function to sum numbers", db_path=temp_db)

    run = get_run(run_id, db_path=temp_db)
    assert run is not None
    assert run["final_status"] == "running"
    assert run["task_description"] == "Write a function to sum numbers"

    # Insert two attempts
    attempt1_id = insert_attempt(
        run_id=run_id,
        attempt_number=1,
        generated_code="def f(): return 1/0",
        stderr="ZeroDivisionError",
        exit_code=1,
        success=False,
        latency_ms=120,
        db_path=temp_db,
    )
    assert attempt1_id > 0

    attempt2_id = insert_attempt(
        run_id=run_id,
        attempt_number=2,
        generated_code="def f(): return sum([1, 2])",
        stdout="3",
        exit_code=0,
        success=True,
        latency_ms=85,
        db_path=temp_db,
    )
    assert attempt2_id > attempt1_id

    update_run_status(run_id, final_status="success", total_attempts=2, db_path=temp_db)

    # Retrieve run with attempts
    full_run = get_run_with_attempts(run_id, db_path=temp_db)
    assert full_run["final_status"] == "success"
    assert full_run["total_attempts"] == 2
    assert len(full_run["attempts"]) == 2
    assert full_run["attempts"][0]["success"] == 0
    assert full_run["attempts"][1]["success"] == 1
    assert full_run["attempts"][1]["stdout"] == "3"


def test_list_runs(temp_db):
    for i in range(3):
        insert_run(f"run-{i}", f"Task {i}", db_path=temp_db)

    runs = list_runs(limit=10, db_path=temp_db)
    assert len(runs) == 3


def test_eval_run_persistence(temp_db):
    eval_id = "eval-2026-09-08"
    insert_eval_run(
        eval_id=eval_id,
        benchmark_name="humaneval",
        pass_at_1=76.5,
        pass_at_5=92.0,
        avg_attempts=1.4,
        total_problems=50,
        raw_json='{"sample": true}',
        db_path=temp_db,
    )

    latest = get_latest_eval_run("humaneval", db_path=temp_db)
    assert latest is not None
    assert latest["eval_id"] == eval_id
    assert latest["pass_at_1"] == 76.5
    assert latest["raw_json"] == '{"sample": true}'
