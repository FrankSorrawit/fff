import asyncio

from core.nodes.input import node_input
from core.nodes.output import node_output
from core.runtime.engine import run_flow
from core.runtime.contracts import NodeContext


async def node_add(ctx: NodeContext):
    """Simple node that increments numeric input by a constant."""

    return ctx.inputs + ctx.params.get("value", 1)


def test_run_flow_sequential():
    flow = {
        "name": "demo",
        "nodes": [
            {"id": "n1", "type": "input", "params": {}},
            {"id": "n2", "type": "add", "params": {"value": 1}},
            {"id": "n3", "type": "output", "params": {}},
        ],
        "edges": [
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
        ],
    }

    events = []
    handlers = {
        "input": node_input,
        "add": node_add,
        "output": node_output,
    }

    result = asyncio.run(run_flow(flow, 0, handlers, emit=lambda e: events.append(e)))

    assert result == 1
    assert [e["node_id"] for e in events] == [
        "n1",
        "n1",
        "n2",
        "n2",
        "n3",
        "n3",
    ]
    assert [e["type"] for e in events] == [
        "step_started",
        "step_succeeded",
        "step_started",
        "step_succeeded",
        "step_started",
        "step_succeeded",
    ]
