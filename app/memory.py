# ── app/memory.py ───────────────────────────────────────────
# Vector memory layer — ChromaDB.
#
# Audited: store_failure() and retrieve_similar_failures() exist
# but were not wired into generator.py or the main repair loop.
# Day 8 wires retrieve_similar_failures() into generator.py for prompt injection
# and ensures terminal failures are saved to ChromaDB.

import os
import uuid
from datetime import datetime
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from app.config import (
    MEMORY_COLLECTION,
    MEMORY_DIR,
    MEMORY_SIMILARITY_THRESHOLD,
    MEMORY_TOP_K,
)

_client: Any = None
_embed_fn: Any = None
_collection: Any = None


def _get_collection(collection_override=None):
    """Lazily load persistent ChromaDB client and all-MiniLM-L6-v2 embedding model."""
    if collection_override is not None:
        return collection_override

    global _client, _embed_fn, _collection
    if _collection is None:
        if _client is None:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            _client = chromadb.PersistentClient(path=MEMORY_DIR)
        if _embed_fn is None:
            _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        _collection = _client.get_or_create_collection(
            name=MEMORY_COLLECTION,
            embedding_function=_embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def store_failure(task: str, code: str, error: str, collection=None) -> str:
    """
    Store a failed attempt in vector memory.
    The embedded document is task + error combined so retrieval
    finds similar TASKS with similar ERRORS, not just similar task wording.
    Returns the memory ID.
    """
    coll = _get_collection(collection)
    memory_id = str(uuid.uuid4())
    document = f"TASK: {task}\nERROR: {error}"

    coll.add(
        ids=[memory_id],
        documents=[document],
        metadatas=[{
            "task": task,
            "code": code,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }],
    )
    return memory_id


def retrieve_similar_failures(
    task: str,
    top_k: int = MEMORY_TOP_K,
    similarity_threshold: float = MEMORY_SIMILARITY_THRESHOLD,
    collection=None,
) -> list[dict[str, Any]]:
    """
    Find the most semantically similar past failures for a given task.
    Returns a list of dicts: { task, code, error, similarity }
    Only includes results above similarity_threshold (default 0.75).
    Returns empty list if memory is empty.
    """
    coll = _get_collection(collection)
    count = coll.count()
    if count == 0:
        return []

    n_results = min(top_k, count)
    results = coll.query(
        query_texts=[task],
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    memories: list[dict[str, Any]] = []
    if results and results.get("metadatas") and results.get("distances"):
        for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
            similarity = 1.0 - distance  # cosine distance → similarity
            if similarity >= similarity_threshold:
                memories.append({
                    "task": meta["task"],
                    "code": meta["code"],
                    "error": meta["error"],
                    "similarity": round(similarity, 3),
                })

    return memories


def build_memory_context(
    task: str,
    top_k: int = MEMORY_TOP_K,
    similarity_threshold: float = MEMORY_SIMILARITY_THRESHOLD,
    collection=None,
) -> str:
    """
    Build a text block of past failures for injection into the generator prompt.
    Returns empty string if no relevant memories exist above threshold.
    """
    memories = retrieve_similar_failures(
        task=task,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        collection=collection,
    )
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


def memory_stats(collection=None) -> dict[str, Any]:
    """Return basic stats about what's stored in memory."""
    coll = _get_collection(collection)
    return {
        "total_failures_stored": coll.count(),
        "memory_dir": os.path.abspath(MEMORY_DIR),
    }


def clear_memory(collection=None) -> None:
    """Wipe all stored memories. Use with caution."""
    global _client, _collection, _embed_fn
    if collection is not None:
        # Clear mock/override collection
        return
    if _client is not None:
        try:
            _client.delete_collection(MEMORY_COLLECTION)
        except Exception:
            pass
    _collection = None
