# ── app/memory.py ───────────────────────────────────────────
# Vector memory layer — ChromaDB.
#
# Two kinds of memories:
#   failure — a task that never passed: what was tried and how it broke
#   fix     — a task that failed first and then passed: the error and the lesson
# Recalled memories are shown to the generator as fenced reference data, never as
# instructions. Embeddings use Chroma's bundled ONNX MiniLM model (no torch needed).

import os
import re
import threading
import uuid
from datetime import datetime
from typing import Any

from app.config import (
    MEMORY_DIR,
    MEMORY_MAX_CHARS,
    MEMORY_SIMILARITY_THRESHOLD,
    MEMORY_TOP_K,
)

MEMORY_COLLECTION = "agent_memory_v2"
# Above this cosine similarity (task + error signature) two memories are the same memory
DUPLICATE_SIMILARITY = 0.97


class MemoryUnavailable(RuntimeError):
    """The vector store can't be opened; callers degrade instead of failing the request."""
_FIELD_LIMITS = {"task": 400, "code": 1200, "error": 600, "lesson": 600}

_client: Any = None
_collection: Any = None
_init_lock = threading.Lock()


def _trim(text: str | None, limit: int) -> str:
    text = (text or "").replace("</recalled_memory>", "")
    return text if len(text) <= limit else text[:limit] + " …[trimmed]"


def error_signature(error: str | None) -> str:
    """Reduce a traceback to a stable 'ExceptionType: message' line with numbers masked."""
    lines = [ln.strip() for ln in (error or "").strip().splitlines() if ln.strip()]
    # The exception can sit mid-line ("- test_x failed: urllib.error.URLError: ..."), so
    # search rather than anchor, and drop the module path so the same error always matches.
    pattern = re.compile(r"(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*(?:Error|Exception|Exit|Interrupt))\b(.*)")
    found = [m for m in (pattern.search(ln) for ln in lines) if m]
    line = (found[-1].group(1) + found[-1].group(2)) if found else (lines[-1] if lines else "unknown failure")
    return re.sub(r"\d+", "N", line)[:200]


def _get_collection(collection_override=None):
    """Lazily create the persistent client and collection."""
    if collection_override is not None:
        return collection_override

    global _client, _collection
    if _collection is not None:
        return _collection
    # Chroma's local backend breaks if several threads open it at the same moment, and then
    # keeps serving the broken client from its cache. Open it once, behind a lock.
    with _init_lock:
        if _collection is not None:
            return _collection
        import chromadb
        from chromadb.utils import embedding_functions

        try:
            if _client is None:
                os.makedirs(MEMORY_DIR, exist_ok=True)
                _client = chromadb.PersistentClient(path=MEMORY_DIR)
            _collection = _client.get_or_create_collection(
                name=MEMORY_COLLECTION,
                embedding_function=embedding_functions.DefaultEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            _client = None
            try:  # drop the half-started client so the next attempt starts clean
                chromadb.api.client.SharedSystemClient.clear_system_cache()
            except Exception:
                pass
            raise MemoryUnavailable(
                f"The memory store at {MEMORY_DIR} could not be opened ({type(e).__name__}). "
                "If it came from an older chromadb version, point MEMORY_DIR at a new folder."
            ) from e
    return _collection


def _add(kind: str, task: str, error: str, code: str = "", lesson: str = "",
         workspace: str = "default", collection=None) -> str:
    coll = _get_collection(collection)
    memory_id = str(uuid.uuid4())
    task = _trim(task, _FIELD_LIMITS["task"])
    error = _trim(error, _FIELD_LIMITS["error"])
    document = f"TASK: {task}\nERROR: {error_signature(error)}"
    fields = {
        "kind": kind,
        "task": task,
        "code": _trim(code, _FIELD_LIMITS["code"]),
        "error": error,
        "signature": error_signature(error),
        "lesson": _trim(lesson, _FIELD_LIMITS["lesson"]),
        "workspace": workspace,
        "timestamp": datetime.now().isoformat(),
    }

    # The same task failing the same way again is the same memory, seen once more
    twin = _find_duplicate(coll, document, kind, workspace)
    if twin is not None:
        twin_id, old = twin
        coll.update(ids=[twin_id], metadatas=[{**old, **fields, "seen": int(old.get("seen", 1)) + 1}])
        return twin_id

    coll.add(
        ids=[memory_id],
        documents=[document],
        metadatas=[{**fields, "uses": 0, "seen": 1, "pinned": False}],
    )
    return memory_id


def _find_duplicate(coll, document: str, kind: str, workspace: str) -> tuple[str, dict] | None:
    try:
        if not coll.count():
            return None
        res = coll.query(
            query_texts=[document],
            n_results=1,
            where={"$and": [{"workspace": workspace}, {"kind": kind}]},
            include=["metadatas", "distances"],
        )
        if res["ids"] and res["ids"][0] and 1.0 - res["distances"][0][0] >= DUPLICATE_SIMILARITY:
            return res["ids"][0][0], dict(res["metadatas"][0][0])
    except Exception:
        pass  # deduplication is a nicety; never let it block remembering
    return None


def store_failure(task: str, code: str, error: str, collection=None, workspace: str = "default") -> str:
    """Store a task that never passed. The document embeds task + error signature."""
    return _add("failure", task, error, code=code, workspace=workspace, collection=collection)


def store_lesson(task: str, error: str, lesson: str, code: str = "", collection=None,
                 workspace: str = "default") -> str:
    """Store what fixed a failure, so similar tasks can avoid the mistake up front."""
    return _add("fix", task, error, code=code, lesson=lesson, workspace=workspace, collection=collection)


def retrieve_similar_failures(
    task: str,
    top_k: int = MEMORY_TOP_K,
    similarity_threshold: float = MEMORY_SIMILARITY_THRESHOLD,
    collection=None,
    workspace: str | None = None,
) -> list[dict[str, Any]]:
    """
    Find the most semantically similar memories for a task (both kinds).
    Returns dicts: { id, kind, task, code, error, lesson, similarity }, above the threshold only.
    """
    coll = _get_collection(collection)
    count = coll.count()
    if count == 0:
        return []

    query: dict[str, Any] = {
        "query_texts": [task],
        "n_results": min(top_k, count),
        "include": ["metadatas", "distances"],
    }
    if workspace:
        query["where"] = {"workspace": workspace}
    results = coll.query(**query)

    memories: list[dict[str, Any]] = []
    if results and results.get("metadatas") and results.get("distances"):
        ids = (results.get("ids") or [[None] * len(results["metadatas"][0])])[0]
        for mem_id, meta, distance in zip(ids, results["metadatas"][0], results["distances"][0]):
            similarity = 1.0 - distance  # cosine distance → similarity
            if similarity >= similarity_threshold:
                memories.append({
                    "id": mem_id,
                    "kind": meta.get("kind", "failure"),
                    "task": meta.get("task", ""),
                    "code": meta.get("code", ""),
                    "error": meta.get("error", ""),
                    "lesson": meta.get("lesson", ""),
                    "similarity": round(similarity, 3),
                })
    return memories


def mark_used(memory_ids: list[str], collection=None) -> None:
    """Bump the usage counter of recalled memories (best effort)."""
    ids = [i for i in memory_ids if i]
    if not ids:
        return
    try:
        coll = _get_collection(collection)
        got = coll.get(ids=ids, include=["metadatas"])
        metas = [{**m, "uses": int(m.get("uses", 0)) + 1} for m in got["metadatas"]]
        coll.update(ids=got["ids"], metadatas=metas)
    except Exception:
        pass


def format_memories(memories: list[dict[str, Any]]) -> str:
    """Render recalled memories as the size-capped reference block for the prompt."""
    if not memories:
        return ""
    lines = ["PAST FAILURES TO AVOID (learn from these mistakes):\n"]
    used = len(lines[0])
    for i, m in enumerate(memories, 1):
        parts = [
            f"[Memory {i} — similarity: {m['similarity']}]",
            f"Task: {_trim(m['task'], _FIELD_LIMITS['task'])}",
        ]
        if m.get("kind") == "fix" and m.get("lesson"):
            parts.append(f"What broke: {_trim(m['error'], _FIELD_LIMITS['error'])}")
            parts.append(f"What fixed it: {_trim(m['lesson'], _FIELD_LIMITS['lesson'])}")
        else:
            parts.append(f"What was tried:\n{_trim(m['code'], _FIELD_LIMITS['code'])}")
            parts.append(f"What went wrong: {_trim(m['error'], _FIELD_LIMITS['error'])}")
            parts.append("Do not repeat this approach.\n")
        entry = "\n".join(parts)
        if used + len(entry) > MEMORY_MAX_CHARS:
            break
        lines.append(entry)
        used += len(entry)
    return "\n".join(lines) if len(lines) > 1 else ""


def build_memory_context(
    task: str,
    top_k: int = MEMORY_TOP_K,
    similarity_threshold: float = MEMORY_SIMILARITY_THRESHOLD,
    collection=None,
) -> str:
    """Text block of relevant memories, or empty string when none clear the threshold."""
    return format_memories(retrieve_similar_failures(
        task=task, top_k=top_k, similarity_threshold=similarity_threshold, collection=collection,
    ))


def list_memories(limit: int = 50, offset: int = 0, kind: str | None = None,
                  workspace: str | None = None, collection=None) -> dict[str, Any]:
    """Page through stored memories, newest first."""
    coll = _get_collection(collection)
    where: dict[str, Any] = {}
    if kind:
        where["kind"] = kind
    if workspace:
        where["workspace"] = workspace
    if len(where) > 1:
        where = {"$and": [{k: v} for k, v in where.items()]}
    got = coll.get(where=where or None, include=["metadatas"])
    items = [{"id": i, **m} for i, m in zip(got["ids"], got["metadatas"])]
    # Newest first, then pinned ones float to the top (sort is stable)
    items.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    items.sort(key=lambda m: not m.get("pinned"))
    return {"total": len(items), "items": items[offset: offset + limit]}


def _owned(got: dict, workspace: str | None) -> bool:
    if not got["ids"]:
        return False
    return workspace is None or got["metadatas"][0].get("workspace", "default") == workspace


def delete_memory(memory_id: str, collection=None, workspace: str | None = None) -> bool:
    coll = _get_collection(collection)
    if not _owned(coll.get(ids=[memory_id], include=["metadatas"]), workspace):
        return False
    coll.delete(ids=[memory_id])
    return True


def set_pinned(memory_id: str, pinned: bool, collection=None, workspace: str | None = None) -> bool:
    coll = _get_collection(collection)
    got = coll.get(ids=[memory_id], include=["metadatas"])
    if not _owned(got, workspace):
        return False
    coll.update(ids=[memory_id], metadatas=[{**got["metadatas"][0], "pinned": pinned}])
    return True


def memory_stats(collection=None, workspace: str | None = None) -> dict[str, Any]:
    coll = _get_collection(collection)
    got = coll.get(where={"workspace": workspace} if workspace else None, include=["metadatas"])
    kinds = [m.get("kind", "failure") for m in got["metadatas"]]
    return {
        "total": len(kinds),
        "failures": kinds.count("failure"),
        "fixes": kinds.count("fix"),
        "times_recalled": sum(int(m.get("uses", 0)) for m in got["metadatas"]),
    }


def clear_memory(collection=None) -> None:
    """Wipe all stored memories. Use with caution."""
    global _collection
    if collection is not None:
        return
    if _client is not None:
        try:
            _client.delete_collection(MEMORY_COLLECTION)
        except Exception:
            pass
    _collection = None
