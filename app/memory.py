# ── app/memory.py ───────────────────────────────────────────
# Vector memory layer — ChromaDB.
# Moved from root memory.py into app/ with updated imports.
#
# Current state (Day 1 baseline):
#   - store_failure() writes failures to ChromaDB ✅
#   - retrieve_similar_failures() reads them back ✅
#   - build_memory_context() formats them for prompt injection ✅
#   - BUT: nothing in the generation loop actually calls
#     build_memory_context() or passes it to the LLM. ❌
#
# Day 8 TODO: wire retrieve_similar_failures() into generator.py
# so past failures actually appear in the LLM prompt, and write
# a test that asserts on the constructed prompt — not just that
# ChromaDB has rows (this was the SheetSense RAG anti-pattern).

import os
import uuid
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions

from app.config import MEMORY_COLLECTION, MEMORY_DIR, MEMORY_SIMILARITY_THRESHOLD, MEMORY_TOP_K

# PersistentClient saves everything to disk — survives restarts
_client = chromadb.PersistentClient(path=MEMORY_DIR)

# sentence-transformers/all-MiniLM-L6-v2:
# Downloads once (~80MB), runs locally, zero API cost
_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_collection = _client.get_or_create_collection(
    name=MEMORY_COLLECTION,
    embedding_function=_embed_fn,
    metadata={"hnsw:space": "cosine"},
)


def store_failure(task: str, code: str, error: str) -> str:
    """
    Store a failed attempt in vector memory.
    The embedded document is task + error combined so retrieval
    finds similar TASKS with similar ERRORS, not just similar task wording.
    Returns the memory ID.
    """
    memory_id = str(uuid.uuid4())
    document = f"TASK: {task}\nERROR: {error}"

    _collection.add(
        ids=[memory_id],
        documents=[document],
        metadatas=[{
            "task":      task,
            "code":      code,
            "error":     error,
            "timestamp": datetime.now().isoformat(),
        }]
    )
    return memory_id


def retrieve_similar_failures(task: str, top_k: int = MEMORY_TOP_K) -> list[dict]:
    """
    Find the most semantically similar past failures for a given task.

    Returns a list of dicts: { task, code, error, similarity }
    Only includes results above MEMORY_SIMILARITY_THRESHOLD (default 0.75 after Day 8).
    Returns empty list if memory is empty.
    """
    count = _collection.count()
    if count == 0:
        return []

    n_results = min(top_k, count)
    results = _collection.query(
        query_texts=[task],
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    memories = []
    for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
        similarity = 1 - distance  # cosine distance → similarity
        if similarity > MEMORY_SIMILARITY_THRESHOLD:
            memories.append({
                "task":       meta["task"],
                "code":       meta["code"],
                "error":      meta["error"],
                "similarity": round(similarity, 3),
            })

    return memories


def build_memory_context(task: str) -> str:
    """
    Build a text block of past failures for injection into the generator prompt.
    Returns empty string if no relevant memories exist.

    Day 8: generator.py will call this and pass the result into build_messages().
    """
    memories = retrieve_similar_failures(task)
    if not memories:
        return ""

    lines = ["PAST FAILURES TO AVOID (learn from these mistakes):\n"]
    for i, m in enumerate(memories, 1):
        lines.append(f"[Memory {i} — similarity: {m['similarity']}]")
        lines.append(f"Task: {m['task']}")
        lines.append(f"What was tried:\n{m['code']}")
        lines.append(f"What went wrong: {m['error']}")
        lines.append("Do not repeat this approach.\n")

    return "\n".join(lines)


def memory_stats() -> dict:
    """Return basic stats about what's stored in memory."""
    return {
        "total_failures_stored": _collection.count(),
        "memory_dir": os.path.abspath(MEMORY_DIR),
    }


def clear_memory() -> None:
    """Wipe all stored memories. Use with caution."""
    _client.delete_collection(MEMORY_COLLECTION)
    global _collection
    _collection = _client.get_or_create_collection(
        name=MEMORY_COLLECTION,
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
