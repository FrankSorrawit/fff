from __future__ import annotations

from core.runtime.contracts import NodeContext
from core import vector_store


async def node_rag_retrieve(ctx: NodeContext):
    """Retrieve relevant chunks from the in-memory vector store.

    The implementation is intentionally lightweight: it delegates embedding and
    vector search to :mod:`core.vector_store`, allowing the tests to monkeypatch
    those functions or use the provided in-memory implementation.  The node
    returns the retrieved chunks together with a list of citation dictionaries
    as described in the prototype specification.
    """

    query_text = (
        ctx.inputs.get("message") if isinstance(ctx.inputs, dict) else str(ctx.inputs)
    )
    embedding = await vector_store.embed(query_text)
    chunks = await vector_store.query(
        embedding, top_k=ctx.params["top_k"], filters=ctx.params.get("filters", {})
    )
    ctx.logger(f"retrieved {len(chunks)} chunks")
    citations = [
        {"source": c.get("meta", {}).get("source"), "page": c.get("meta", {}).get("page")}
        for c in chunks
    ]
    return {"chunks": chunks, "citations": citations}

