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
    from app.db import close_pooled_connections

    close_pooled_connections()
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


def test_critique_columns_and_review_update(temp_db):
    run_id = "test-critique-run"
    insert_run(run_id, "Write a binary search", db_path=temp_db)

    att_id = insert_attempt(
        run_id=run_id,
        attempt_number=1,
        generated_code="def search(): pass",
        critique_confidence=0.25,
        critique_reasoning="Intractable recursive depth logic",
        success=False,
        db_path=temp_db,
    )

    from app.db import update_attempt_review

    update_attempt_review(
        attempt_id=att_id,
        critique_confidence=0.88,
        critique_reasoning="Revised logic is solid",
        generated_tests="def test_search(): assert search() is None",
        db_path=temp_db,
    )

    run = get_run_with_attempts(run_id, db_path=temp_db)
    attempt = run["attempts"][0]
    assert attempt["critique_confidence"] == 0.88
    assert attempt["critique_reasoning"] == "Revised logic is solid"
    assert "test_search" in attempt["generated_tests"]


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


def test_connections_are_pooled_per_thread(temp_db):
    import threading

    from app.db import get_connection

    with get_connection(temp_db) as first:
        pass
    with get_connection(temp_db) as second:
        pass
    assert first is second

    other = []
    t = threading.Thread(target=lambda: other.append(get_connection(temp_db).__enter__()))
    t.start()
    t.join()
    assert other[0] is not first  # SQLite connections never cross threads


def test_nested_use_gets_its_own_connection_and_failures_roll_back(temp_db):
    from app.db import get_connection, get_run, insert_run

    # Nested use in one thread never shares (and so never commits) the outer transaction
    with get_connection(temp_db) as outer:
        outer.execute("SELECT 1").fetchone()
        with get_connection(temp_db) as inner:
            assert inner is not outer
        insert_run("r_inner", "t", db_path=temp_db)
    assert get_run("r_inner", db_path=temp_db) is not None

    # A block that fails rolls back its own write, and the pooled connection stays usable
    with pytest.raises(RuntimeError):
        with get_connection(temp_db) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, task_description, created_at, final_status) VALUES ('r_rb', 't', 'now', 'x')"
            )
            raise RuntimeError("block fails")
    assert get_run("r_rb", db_path=temp_db) is None
    insert_run("r_after", "t", db_path=temp_db)
    assert get_run("r_after", db_path=temp_db) is not None


def test_run_summaries_aggregate_attempts_for_the_page(temp_db):
    from app.db import insert_attempt, insert_run, list_run_summaries

    insert_run("r_sum", "task", final_status="success", total_attempts=2, db_path=temp_db)
    insert_attempt("r_sum", 1, "a", success=False, latency_ms=100, db_path=temp_db)
    insert_attempt("r_sum", 2, "b", success=True, latency_ms=250, quality_overall_score=0.9, db_path=temp_db)
    insert_run("r_none", "no attempts", db_path=temp_db)
    items = {i["run_id"]: i for i in list_run_summaries(db_path=temp_db)["items"]}
    assert items["r_sum"]["passed_on_attempt"] == 2
    assert items["r_sum"]["total_latency_ms"] == 350 and items["r_sum"]["quality_score"] == 0.9
    assert items["r_none"]["passed_on_attempt"] is None and items["r_none"]["total_latency_ms"] == 0
