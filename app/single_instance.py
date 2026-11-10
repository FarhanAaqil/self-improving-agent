"""One API process per data directory, enforced.

Background runs, the rate limiter and the vector store all live in this process, and
ChromaDB's on-disk store is not safe for several writers. Rather than leave that as a
footnote, a second process pointed at the same data refuses to start. To scale out,
give each instance its own DB_PATH and MEMORY_DIR, or put a real queue in front.
"""

import os

from app.config import DB_PATH


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    """An advisory lock on a file next to the database, held for the life of the process."""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.abspath(DB_PATH) + ".lock"
        self._handle = None

    def acquire(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        handle = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            handle.close()
            raise AlreadyRunning(
                f"Another API process is already using {os.path.dirname(self.path)}. "
                "Run a single worker, or give each instance its own DB_PATH and MEMORY_DIR."
            ) from e
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None
