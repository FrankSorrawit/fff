import asyncio

from core.nodes.rag_retrieve import node_rag_retrieve
from core.runtime.contracts import NodeContext
from core import vector_store


def setup_function():
    vector_store.VECTOR_DB.clear()
    asyncio.run(
        vector_store.upsert(
            [
                {
                    "id": "c1",
                    "text": "hello world",
                    "metadata": {"source": "doc1", "page": 1},
                },
                {
                    "id": "c2",
                    "text": "other text",
                    "metadata": {"source": "doc2", "page": 2},
                },
            ]
        )
    )


def test_node_rag_retrieve_basic():
    ctx = NodeContext(
        run_id="r1",
        node_id="n2",
        inputs={"message": "hello world"},
        params={"top_k": 1},
        secrets={},
        user={},
        logger=lambda msg: None,
        emit=lambda evt: None,
        timeout_ms=1000,
    )
    result = asyncio.run(node_rag_retrieve(ctx))
    assert "chunks" in result
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == "hello world"
    assert result["citations"] == [{"source": "doc1", "page": 1}]
