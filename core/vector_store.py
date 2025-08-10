"""Simple in-memory vector store used for tests.

The real project integrates with Vertex AI Vector Search.  For the prototype and
unit tests we provide a very small in-memory approximation with a compatible
interface.  It supports three asynchronous functions:

``create_index_if_not_exists``
    No-op placeholder that mirrors the real API.
``upsert``
    Store a list of chunks in memory.  Each chunk should contain ``text`` and
    optional ``metadata``.  Embeddings are computed automatically using the
    ``embed`` helper.
``query``
    Return the ``top_k`` chunks closest to the provided embedding using a
    euclidean distance metric.  The result format matches the structure expected
    by the runtime's ``rag.retrieve`` node.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# In-memory database
# ---------------------------------------------------------------------------

VECTOR_DB: List[Dict[str, Any]] = []


async def create_index_if_not_exists(index_name: str) -> None:
    """Placeholder to mirror the real vector store API."""

    # The in-memory implementation always exists; nothing to do.
    return None


async def embed(text: str) -> List[float]:
    """Return a trivial embedding for ``text``.

    The function maps the text to a single floating point number derived from
    the ordinal values of its characters.  While obviously not semantically
    meaningful, it is deterministic which suffices for unit tests.
    """

    if not text:
        return [0.0]
    return [sum(ord(ch) for ch in text) / len(text)]


async def upsert(chunks: List[Dict[str, Any]]) -> str:
    """Insert ``chunks`` into the in-memory database.

    Each chunk is expected to contain ``text`` and optional ``metadata``.  A
    simple embedding is generated automatically if not supplied.  The function
    returns a dummy task identifier similar to the asynchronous behaviour of the
    real Vertex service.
    """

    for chunk in chunks:
        if "embedding" not in chunk:
            chunk["embedding"] = await embed(chunk.get("text", ""))
        VECTOR_DB.append(chunk)
    return f"task_{len(VECTOR_DB)}"


async def query(
    embedding: List[float],
    top_k: int,
    filters: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Return the ``top_k`` most similar chunks to ``embedding``.

    ``filters`` are ignored in this simplified implementation but kept for API
    compatibility.  Results are returned in a format suitable for the
    ``rag.retrieve`` node: a list of dicts containing ``text``, ``meta`` and
    ``score`` fields.
    """

    def score(chunk: Dict[str, Any]) -> float:
        emb = chunk.get("embedding", [0.0])
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(embedding, emb)))
        return 1.0 / (1.0 + dist)

    # Ignore filters for the prototype; a real implementation would apply them.
    ordered = sorted(VECTOR_DB, key=score, reverse=True)[:top_k]
    return [
        {"text": c.get("text", ""), "meta": c.get("metadata", {}), "score": score(c)}
        for c in ordered
    ]
