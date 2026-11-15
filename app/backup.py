"""Backups of everything that matters: the SQLite database and the Chroma memory folder.

Taken safely while the app runs:
  * SQLite through its online backup API, which copies a consistent snapshot even while
    other connections write (WAL and all);
  * Chroma by holding the memory module's write lock while its folder is copied, and
    copying its own SQLite file with the same backup API.

Each backup is one archive, backup-YYYYmmdd-HHMMSS.tar.gz, with a manifest (row counts,
memory count, sizes) so a restore can be checked. The running server makes one every
BACKUP_EVERY_HOURS into BACKUP_DIR and keeps the newest BACKUP_KEEP. Copy that folder off
the machine (see docs/DEPLOY.md); a backup on the same disk doesn't survive the disk.

    python -m app.backup create [--dest DIR]       # server stopped (or use POST /admin/backup)
    python -m app.backup verify ARCHIVE            # restore into a temp folder and check it
    python -m app.backup restore ARCHIVE [--force] # server stopped: replace the live data
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

from app import config

logger = logging.getLogger("self_improving_agent.backup")

ARCHIVE_PREFIX = "backup-"
_COUNTED_TABLES = ("runs", "attempts", "run_events", "users", "api_keys")


def _sqlite_copy(src_path: str, dst_path: str) -> None:
    """A consistent copy of a live SQLite database."""
    src = sqlite3.connect(src_path, timeout=30)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def _counts(db_file: str) -> dict[str, int]:
    conn = sqlite3.connect(db_file)
    try:
        out = {}
        for table in _COUNTED_TABLES:
            try:
                out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                out[table] = 0
        return out
    finally:
        conn.close()


def _copy_memory(memory_dir: str, dst: Path) -> None:
    """Copy the Chroma folder; its SQLite files go through the backup API."""
    src = Path(memory_dir)
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if path.name.endswith(("-wal", "-shm")):
            continue  # captured by the SQLite backup of the main file
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in (".sqlite3", ".sqlite", ".db"):
            _sqlite_copy(str(path), str(target))
        else:
            shutil.copy2(path, target)


_COUNT_SCRIPT = """
import sys, chromadb
from app.memory import MEMORY_COLLECTION
client = chromadb.PersistentClient(path=sys.argv[1])
try:
    print(client.get_collection(MEMORY_COLLECTION).count())
except Exception:
    print(0)
"""


def _memory_count(memory_dir: str) -> int | None:
    """How many memories a Chroma folder holds. Opened in a short-lived process: Chroma keeps
    its files open (and memory-mapped) for the life of a client, which would pin a copy."""
    if not Path(memory_dir).exists():
        return None
    root = str(Path(__file__).resolve().parent.parent)
    try:
        out = subprocess.run(
            [sys.executable, "-c", _COUNT_SCRIPT, memory_dir],
            capture_output=True, text=True, timeout=120, cwd=root,
        )
        return int(out.stdout.strip().splitlines()[-1])
    except Exception:
        logger.warning("Could not count memories in %s", memory_dir, exc_info=True)
        return None


def create_backup(dest_dir: str | None = None, db_path: str | None = None, memory_dir: str | None = None) -> Path:
    """Write one archive into dest_dir and return its path."""
    dest = Path(dest_dir or config.BACKUP_DIR)
    if not str(dest):
        raise ValueError("Set BACKUP_DIR (or pass a destination) to make backups.")
    db_path = db_path or config.DB_PATH
    memory_dir = memory_dir or config.MEMORY_DIR
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = dest / f"{ARCHIVE_PREFIX}{stamp}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="agent-backup-") as tmp:
        staging = Path(tmp)
        _sqlite_copy(db_path, str(staging / "agent.db"))
        memories = None
        if Path(memory_dir).exists():
            try:
                from app import memory

                lock = memory.write_lock
            except Exception:
                lock = nullcontext()
            with lock:  # no memory writes while its files are copied
                _copy_memory(memory_dir, staging / "memory")
            memories = _memory_count(str(staging / "memory"))
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "db_rows": _counts(str(staging / "agent.db")),
            "memories": memories,
            "has_memory": (staging / "memory").exists(),
            "format": 1,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        partial = archive.with_suffix(".partial")
        with tarfile.open(partial, "w:gz") as tar:
            for item in sorted(staging.iterdir()):
                tar.add(item, arcname=item.name)
        os.replace(partial, archive)  # a half-written archive never looks like a backup
    logger.info("Backup written: %s (%s)", archive, manifest["db_rows"])
    return archive


def list_backups(dest_dir: str | None = None) -> list[Path]:
    dest = Path(dest_dir or config.BACKUP_DIR)
    if not dest.exists():
        return []
    return sorted(dest.glob(f"{ARCHIVE_PREFIX}*.tar.gz"))


def prune(dest_dir: str | None = None, keep: int | None = None) -> int:
    keep = config.BACKUP_KEEP if keep is None else keep
    old = list_backups(dest_dir)[:-keep] if keep > 0 else []
    for path in old:
        path.unlink(missing_ok=True)
    return len(old)


def backup_due(dest_dir: str | None = None, every_hours: float | None = None, now: float | None = None) -> bool:
    existing = list_backups(dest_dir)
    if not existing:
        return True
    age = (now or time.time()) - existing[-1].stat().st_mtime
    return age >= (every_hours or config.BACKUP_EVERY_HOURS) * 3600


def scheduled_backup() -> Path | None:
    """The maintenance chore: back up when the newest backup is old enough, then prune."""
    if not config.BACKUP_DIR or not backup_due():
        return None
    path = create_backup()
    prune()
    return path


def _safe_extract(archive: Path, target: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            resolved = (target / member.name).resolve()
            if not str(resolved).startswith(str(target.resolve())) or member.issym() or member.islnk():
                raise ValueError(f"Refusing to extract a suspicious path from the archive: {member.name}")
        # Every member was checked above; the "data" filter (Python 3.12+) is a second guard
        if hasattr(tarfile, "data_filter"):
            tar.extractall(target, filter="data")
        else:  # pragma: no cover - Python 3.11
            tar.extractall(target)  # noqa: S202


def verify_backup(archive: str | Path) -> dict:
    """Restore into a temporary folder and check it: SQLite integrity, row counts and the
    memory count all have to match the manifest. Returns the findings; raises if broken."""
    archive = Path(archive)
    with tempfile.TemporaryDirectory(prefix="agent-restore-test-") as tmp:
        target = Path(tmp)
        _safe_extract(archive, target)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        conn = sqlite3.connect(target / "agent.db")
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        rows = _counts(str(target / "agent.db"))
        if rows != manifest["db_rows"]:
            raise RuntimeError(f"Row counts differ from the manifest: {rows} vs {manifest['db_rows']}")
        memories = _memory_count(str(target / "memory")) if manifest.get("has_memory") else None
        if manifest.get("memories") is not None and memories != manifest["memories"]:
            raise RuntimeError(f"Memory count differs: {memories} vs {manifest['memories']}")
        return {"archive": str(archive), "integrity": integrity, "db_rows": rows, "memories": memories,
                "created_at": manifest["created_at"]}


def restore_backup(archive: str | Path, db_path: str | None = None, memory_dir: str | None = None,
                   force: bool = False) -> dict:
    """Replace the live data with a backup. The server must be stopped (the instance lock
    is taken to make sure). The current data is moved aside, not deleted."""
    from app.single_instance import InstanceLock

    findings = verify_backup(archive)
    db_path = db_path or config.DB_PATH
    memory_dir = memory_dir or config.MEMORY_DIR
    lock = InstanceLock(os.path.abspath(db_path) + ".lock")
    lock.acquire()  # raises if a server still owns this data
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if Path(db_path).exists() or Path(memory_dir).exists():
            if not force and Path(db_path).exists() and _counts(db_path).get("runs"):
                raise RuntimeError("The live database has data. Pass --force to move it aside and restore.")
        with tempfile.TemporaryDirectory(prefix="agent-restore-") as tmp:
            target = Path(tmp)
            _safe_extract(Path(archive), target)
            for suffix in ("", "-wal", "-shm"):
                live = Path(db_path + suffix)
                if live.exists():
                    live.rename(f"{db_path}{suffix}.before-restore-{stamp}")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target / "agent.db", db_path)
            if (target / "memory").exists():
                if Path(memory_dir).exists():
                    Path(memory_dir).rename(f"{memory_dir}.before-restore-{stamp}")
                shutil.copytree(target / "memory", memory_dir)
    finally:
        lock.release()
    return findings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.backup", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="make a backup now (stop the server first, or use POST /admin/backup)")
    create.add_argument("--dest", default=None)
    verify = sub.add_parser("verify", help="restore a backup into a temp folder and check it")
    verify.add_argument("archive")
    restore = sub.add_parser("restore", help="replace the live data with a backup (server stopped)")
    restore.add_argument("archive")
    restore.add_argument("--force", action="store_true", help="move existing data aside even if it has runs")
    args = parser.parse_args(argv)

    if args.command == "create":
        print(create_backup(args.dest))
    elif args.command == "verify":
        print(json.dumps(verify_backup(args.archive), indent=2))
        print("Restore test passed.")
    elif args.command == "restore":
        try:
            findings = restore_backup(args.archive, force=args.force)
        except RuntimeError as exc:
            sys.exit(str(exc))
        print(json.dumps(findings, indent=2))
        print("Restored. Start the server.")


if __name__ == "__main__":
    main()
