# ── memory.py ──────────────────────────────────────────────
# Week 3: Persistent Vector Memory
#
# What this does:
#   Every time the agent fails to solve something, that failure
#   (task + broken code + error) is stored as a vector embedding.
#
#   On the NEXT run, before generating code, the agent retrieves
#   the top-K most similar past failures and injects them as
#   context — so it never makes the same mistake twice.
#
# Storage: ChromaDB runs 100% locally in a folder called memory_db/
# Embeddings: sentence-transformers runs locally, no API calls needed
# Cost: completely free, works offline

import os
import uuid
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions
from config import MEMORY_DIR, MEMORY_COLLECTION, MEMORY_TOP_K

# ── Setup ────────────────────────────────────────────────────
# PersistentClient saves everything to disk — survives restarts
_client = chromadb.PersistentClient(path=MEMORY_DIR)

# sentence-transformers/all-MiniLM-L6-v2:
#   - Downloads once (~80MB), runs locally forever
#   - Fast, good semantic similarity for code + error text
_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_collection = _client.get_or_create_collection(
    name=MEMORY_COLLECTION,
    embedding_function=_embed_fn,
    metadata={"hnsw:space": "cosine"},  # cosine similarity for text
)


# ── Public API ───────────────────────────────────────────────

def store_failure(task: str, code: str, error: str) -> str:
    """
    Store a failed attempt in vector memory.

    The document embedded is: task + error combined.
    This way retrieval finds similar TASKS with similar ERRORS —
    not just similar task wording.

    Returns the memory ID for reference.
    """
    memory_id = str(uuid.uuid4())
    document  = f"TASK: {task}\nERROR: {error}"

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

    Returns a list of dicts:
        { task, code, error, similarity_score }

    Returns empty list if memory is empty or no good matches found.
    """
    count = _collection.count()
    if count == 0:
        return []

    # Don't ask for more results than exist
    n_results = min(top_k, count)

    results = _collection.query(
        query_texts=[task],
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    memories = []
    for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
        similarity = 1 - distance  # cosine distance → similarity score
        if similarity > 0.3:       # threshold — ignore very dissimilar memories
            memories.append({
                "task":       meta["task"],
                "code":       meta["code"],
                "error":      meta["error"],
                "similarity": round(similarity, 3),
            })

    return memories


def build_memory_context(task: str) -> str:
    """
    Build a text block of past failures to inject into the generator prompt.
    Returns empty string if no relevant memories exist.

    Example output injected into the LLM:
        PAST FAILURES TO AVOID:

        [Memory 1 — similarity: 0.87]
        Task: Write a binary search function
        What was tried: def binary_search(arr, target): ...
        What went wrong: IndexError: list index out of range
        Do not repeat this approach.

        [Memory 2 — similarity: 0.71]
        ...
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


def clear_memory():
    """Wipe all stored memories. Use with caution."""
    _client.delete_collection(MEMORY_COLLECTION)
    global _collection
    _collection = _client.get_or_create_collection(
        name=MEMORY_COLLECTION,
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )