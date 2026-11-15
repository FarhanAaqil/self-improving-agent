"""Phase 6: backups and restore, admin controls, abuse limits, logs and error tracking."""

import io
import json
import logging
import sqlite3
import subprocess
import sys
import tarfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import accounts, backup, config, db, errors
from app.main import app
from app.observability import JsonFormatter
from app.security import RateLimiter
from app.single_instance import InstanceLock
from tests.accounts_helpers import OWN_GROQ_KEY, SignedIn, new_email

TASK = {"task_description": "Write solve() returning 42"}
ROOT = str(Path(__file__).resolve().parent.parent)
_SEED_MEMORY = """
import sys, chromadb
from app.memory import MEMORY_COLLECTION
coll = chromadb.PersistentClient(path=sys.argv[1]).get_or_create_collection(
    MEMORY_COLLECTION, metadata={"hnsw:space": "cosine"})
coll.add(ids=["m1", "m2"], documents=["TASK: a", "TASK: b"], embeddings=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
         metadatas=[{"workspace": "u_bk"}, {"workspace": "u_bk"}])
"""


@pytest.fixture(autouse=True)
def accounts_only(monkeypatch):
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


# ── Backups ──────────────────────────────────────────────────


def make_live_data(tmp_path: Path) -> tuple[str, str]:
    """A small 'production' database and memory store, as a running server would have."""
    db_path = str(tmp_path / "live" / "agent.db")
    memory_dir = str(tmp_path / "live" / "memory")
    db.init_db(db_path)
    for i in range(3):
        db.insert_run(f"run_bk_{i}", "Write add(a, b)", final_status="success", db_path=db_path)
        db.insert_attempt(run_id=f"run_bk_{i}", attempt_number=1, generated_code="def add(a, b): return a + b",
                          success=True, db_path=db_path)
    with db.get_connection(db_path) as conn:
        conn.execute("INSERT INTO users (user_id, email, password_hash, created_at, active) "
                     "VALUES ('u_bk', 'bk@example.com', 'x', '2026-01-01', 1)")
    # Written by another process, like the server would, so this test holds no Chroma files open
    subprocess.run([sys.executable, "-c", _SEED_MEMORY, memory_dir], check=True, cwd=ROOT, timeout=120)
    db.close_pooled_connections()  # a stopped server holds no connections either
    return db_path, memory_dir


def test_backup_and_restore_onto_a_fresh_machine(tmp_path):
    db_path, memory_dir = make_live_data(tmp_path)
    archive = backup.create_backup(str(tmp_path / "backups"), db_path=db_path, memory_dir=memory_dir)
    assert archive.name.startswith("backup-") and archive.suffixes[-2:] == [".tar", ".gz"]

    findings = backup.verify_backup(archive)
    assert findings["integrity"] == "ok"
    assert findings["db_rows"]["runs"] == 3 and findings["db_rows"]["users"] == 1
    assert findings["memories"] == 2

    # A brand-new machine: empty data folder
    new_db = str(tmp_path / "fresh" / "agent.db")
    new_mem = str(tmp_path / "fresh" / "memory")
    backup.restore_backup(archive, db_path=new_db, memory_dir=new_mem)
    conn = sqlite3.connect(new_db)
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 3
    assert conn.execute("SELECT email FROM users").fetchone()[0] == "bk@example.com"
    conn.close()
    assert backup._memory_count(new_mem) == 2


def test_backups_are_consistent_while_the_database_is_being_written(tmp_path):
    db_path, memory_dir = make_live_data(tmp_path)
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            db.insert_run(f"run_busy_{i}", "busy", final_status="success", db_path=db_path)
            i += 1

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        archives = [backup.create_backup(str(tmp_path / "b"), db_path=db_path, memory_dir=memory_dir) for _ in range(2)]
    finally:
        stop.set()
        thread.join()
    for archive in archives:
        assert backup.verify_backup(archive)["integrity"] == "ok"


def test_restore_refuses_while_a_server_owns_the_data(tmp_path):
    db_path, memory_dir = make_live_data(tmp_path)
    archive = backup.create_backup(str(tmp_path / "b"), db_path=db_path, memory_dir=memory_dir)
    lock = InstanceLock(str(Path(db_path).resolve()) + ".lock")
    lock.acquire()
    try:
        with pytest.raises(Exception):
            backup.restore_backup(archive, db_path=db_path, memory_dir=memory_dir, force=True)
    finally:
        lock.release()


def test_restore_wont_overwrite_live_data_without_force_and_keeps_it_aside(tmp_path):
    db_path, memory_dir = make_live_data(tmp_path)
    archive = backup.create_backup(str(tmp_path / "b"), db_path=db_path, memory_dir=memory_dir)
    with pytest.raises(RuntimeError, match="--force"):
        backup.restore_backup(archive, db_path=db_path, memory_dir=memory_dir)
    db.close_pooled_connections()
    backup.restore_backup(archive, db_path=db_path, memory_dir=memory_dir, force=True)
    assert list(Path(db_path).parent.glob("agent.db.before-restore-*"))


def test_a_tampered_archive_is_refused(tmp_path):
    evil = tmp_path / "backup-evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        data = b"pwned"
        info = tarfile.TarInfo("../../outside.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError, match="suspicious"):
        backup.verify_backup(evil)
    assert not (tmp_path.parent / "outside.txt").exists()


def test_a_damaged_backup_fails_the_restore_test(tmp_path):
    db_path, memory_dir = make_live_data(tmp_path)
    archive = backup.create_backup(str(tmp_path / "b"), db_path=db_path, memory_dir=memory_dir)
    work = tmp_path / "unpacked"
    work.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(work, filter="data") if hasattr(tarfile, "data_filter") else tar.extractall(work)
    manifest = json.loads((work / "manifest.json").read_text())
    manifest["db_rows"]["runs"] = 999  # the archive no longer matches what it claims
    (work / "manifest.json").write_text(json.dumps(manifest))
    broken = tmp_path / "backup-broken.tar.gz"
    with tarfile.open(broken, "w:gz") as tar:
        for item in work.iterdir():
            tar.add(item, arcname=item.name)
    with pytest.raises(RuntimeError, match="Row counts"):
        backup.verify_backup(broken)


def test_old_backups_are_pruned_and_schedule_respected(tmp_path, monkeypatch):
    db_path, memory_dir = make_live_data(tmp_path)
    dest = tmp_path / "b"
    for i in range(4):
        dest.mkdir(exist_ok=True)
        (dest / f"backup-2026010{i}-000000.tar.gz").write_bytes(b"x")
    assert backup.prune(str(dest), keep=2) == 2
    assert len(backup.list_backups(str(dest))) == 2
    assert backup.backup_due(str(dest), every_hours=24) is False  # fresh files
    assert backup.backup_due(str(tmp_path / "empty"), every_hours=24) is True

    monkeypatch.setattr(config, "BACKUP_DIR", "")
    assert backup.scheduled_backup() is None  # off unless configured


def test_operator_can_take_a_backup_now(tmp_path, monkeypatch):
    with patch("app.config.API_KEY", "operator-secret-key"):
        operator = TestClient(app)
        headers = {"X-API-Key": "operator-secret-key"}
        monkeypatch.setattr(config, "BACKUP_DIR", "")
        assert operator.post("/admin/backup", headers=headers).status_code == 409
        monkeypatch.setattr(config, "BACKUP_DIR", str(tmp_path / "now"))
        resp = operator.post("/admin/backup", headers=headers)
        assert resp.status_code == 200
        assert (tmp_path / "now" / resp.json()["archive"]).exists()
        assert operator.get("/admin/backups", headers=headers).json()["items"]


def test_backup_command_line(tmp_path, capsys):
    db_path, memory_dir = make_live_data(tmp_path)
    archive = backup.create_backup(str(tmp_path / "b"), db_path=db_path, memory_dir=memory_dir)
    backup.main(["verify", str(archive)])
    assert "Restore test passed." in capsys.readouterr().out


# ── Admin page ───────────────────────────────────────────────


def test_admin_emails_get_the_admin_page_and_others_dont(monkeypatch):
    admin = SignedIn(new_email())
    member = SignedIn(new_email())
    monkeypatch.setattr(config, "ADMIN_EMAILS", {admin.email})
    assert admin.get("/auth/me").json()["operator"] is True
    assert member.get("/auth/me").json()["operator"] is False

    listing = admin.get("/admin/users", params={"page_size": 200}).json()
    emails = {u["email"] for u in listing["items"]}
    assert {admin.email, member.email} <= emails
    row = next(u for u in listing["items"] if u["email"] == member.email)
    assert row["effective_plan"] == "free" and row["active"] is True and "runs_today" in row
    assert member.get("/admin/users").status_code == 403


def test_admin_list_shows_usage(monkeypatch):
    admin = SignedIn(new_email())
    member = SignedIn(new_email())
    monkeypatch.setattr(config, "ADMIN_EMAILS", {admin.email})
    db.insert_run("run_adm_usage", "x", final_status="success")
    db.update_run("run_adm_usage", workspace=member.workspace, key_source="server", prompt_tokens=321)
    row = next(u for u in admin.get("/admin/users", params={"q": member.email}).json()["items"])
    assert row["runs_today"] == 1 and row["runs_total"] == 1 and row["server_tokens_today"] == 321


def test_the_disable_switch_cuts_off_sessions_and_keys(monkeypatch):
    admin = SignedIn(new_email())
    member = SignedIn(new_email())
    monkeypatch.setattr(config, "ADMIN_EMAILS", {admin.email})
    key = member.post("/account/keys", json={"name": "k"}).json()["key"]
    assert admin.post(f"/admin/users/{member.user['user_id']}/active", json={"active": False}).status_code == 200
    assert member.get("/runs").status_code == 401
    assert TestClient(app).get("/runs", headers={"X-API-Key": key}).status_code == 401
    assert admin.post(f"/admin/users/{member.user['user_id']}/active", json={"active": True}).status_code == 200
    assert TestClient(app).get("/runs", headers={"X-API-Key": key}).status_code == 200
    assert admin.post(f"/admin/users/{admin.user['user_id']}/active", json={"active": False}).status_code == 409


# ── Abuse: brand-new accounts ────────────────────────────────


def test_accounts_younger_than_a_day_get_a_tighter_rate_limit(monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr("app.security.limiter", RateLimiter(0))
    monkeypatch.setattr("app.security.new_account_limiter", RateLimiter(1))
    fresh = SignedIn(new_email())
    seasoned = SignedIn(new_email())
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET created_at = ? WHERE user_id = ?", (old, seasoned.user["user_id"]))
    with patch("app.main.submit_run"):
        assert fresh.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 202
        assert fresh.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 429
        assert [seasoned.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code for _ in range(3)] == [202] * 3


# ── Logs ─────────────────────────────────────────────────────


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.formatter = JsonFormatter()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(self.format(record))


def test_logs_carry_user_and_request_ids_but_never_keys_or_code():
    user = SignedIn(new_email())
    api_key = user.post("/account/keys", json={"name": "logs"}).json()["key"]
    capture = Capture()
    root = logging.getLogger()
    root.addHandler(capture)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    secret_code = "def secret_function_body(): return 'TOP-SECRET-CODE'"
    try:
        with patch("app.main.submit_run"):
            user.post("/runs", headers={**OWN_GROQ_KEY, "X-Request-ID": "req-abc123"},
                      json={"task_description": secret_code})
            TestClient(app).get("/runs?q=searchterm", headers={"X-API-Key": api_key})
    finally:
        root.removeHandler(capture)
        root.setLevel(old_level)
    text = "\n".join(capture.lines)
    assert OWN_GROQ_KEY["X-Groq-Key"] not in text
    assert api_key not in text and "TOP-SECRET-CODE" not in text and user.password not in text
    access = [json.loads(line) for line in capture.lines if '"self_improving_agent.access"' in line]
    post = next(a for a in access if a.get("method") == "POST")
    assert post["user_id"] == user.user["user_id"] and post["request_id"] == "req-abc123"
    assert post["path"] == "/runs" and post["status_code"] == 202
    assert all("searchterm" not in a["msg"] for a in access)  # query strings stay out


# ── Error tracking ───────────────────────────────────────────


def test_error_tracking_is_off_without_a_dsn(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "")
    with patch("sentry_sdk.init") as init:
        assert errors.init_error_tracking() is False
    init.assert_not_called()


def test_error_tracking_never_sends_bodies_pii_or_locals(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    with patch("sentry_sdk.init") as init:
        assert errors.init_error_tracking() is True
    kwargs = init.call_args.kwargs
    assert kwargs["send_default_pii"] is False
    assert kwargs["max_request_body_size"] == "never"
    assert kwargs["include_local_variables"] is False
    assert kwargs["before_send"] is errors.scrub


def test_scrubber_strips_secrets_from_events():
    event = {
        "request": {
            "headers": {"X-Groq-Key": "gsk_x", "Authorization": "Bearer sia_y", "Cookie": "sia_session=z",
                        "X-CSRF-Token": "t", "User-Agent": "ok"},
            "cookies": {"sia_session": "z"},
            "data": {"task_description": "secret code"},
            "query_string": "q=private",
        },
        "user": {"id": "u_1", "email": "a@example.com", "ip_address": "1.2.3.4"},
        "exception": {"values": [{"stacktrace": {"frames": [{"vars": {"groq_key": "gsk_x"}}]}}]},
        "extra": {"anything": "x"},
    }
    out = errors.scrub(event, {})
    flat = json.dumps(out)
    for secret in ("gsk_x", "sia_y", "sia_session=z", "secret code", "q=private", "a@example.com", "1.2.3.4"):
        assert secret not in flat
    assert out["user"] == {"id": "u_1"} and out["request"]["headers"]["User-Agent"] == "ok"


def test_disabled_accounts_cant_log_in_again():
    user = SignedIn(new_email())
    accounts.set_active(user.user["user_id"], False)
    resp = TestClient(app).post("/auth/login", json={"email": user.email, "password": user.password})
    assert resp.status_code == 403
