import asyncio
import json
from urllib import request

from core.nodes.llm_chat import node_llm_chat
from core.runtime.contracts import NodeContext


class DummyResponse:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_node_llm_chat(monkeypatch):
    def fake_urlopen(req, timeout=10):
        return DummyResponse({"choices": [{"message": {"content": "hi"}}]})

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    ctx = NodeContext(
        run_id="r1",
        node_id="n1",
        inputs={"message": "hello"},
        params={},
        secrets={},
        user={},
        logger=lambda msg: None,
        emit=lambda evt: None,
        timeout_ms=1000,
    )
    result = asyncio.run(node_llm_chat(ctx))
    assert result["text"] == "hi"
