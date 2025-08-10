import pytest

from core.validation import validate_and_repair
from core.node_catalog import NODE_CATALOG


def build_flow():
    return {
        "name": "demo",
        "nodes": [
            {"id": "n1", "type": "input", "params": {}},
            {"id": "n2", "type": "llm.chat", "params": {}},
            {"id": "n3", "type": "output", "params": {}},
        ],
        "edges": [
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
        ],
    }


def test_validate_and_repair_defaults():
    flow = build_flow()
    repaired = validate_and_repair(flow, NODE_CATALOG)
    assert repaired["nodes"][1]["params"] == {
        "model": "gpt-4o-mini",
        "system": "Answer concisely.",
        "temperature": 0.2,
    }


@pytest.mark.parametrize(
    "mutator,code",
    [
        (lambda f: f["nodes"].append({"id": "n1", "type": "input", "params": {}}), "DUPLICATE_NODE_ID"),
        (lambda f: f["edges"].append({"from": "n99", "to": "n1"}), "EDGE_REF_INVALID"),
        (lambda f: f["nodes"][0].update({"type": "llm.chat"}), "FIRST_NODE_MUST_BE_INPUT"),
        (lambda f: f["nodes"][-1].update({"type": "llm.chat"}), "LAST_NODE_MUST_BE_OUTPUT"),
        (lambda f: f["edges"].append({"from": "n1", "to": "n3"}), "MULTI_IN_NOT_ALLOWED"),
    ],
)
def test_validate_and_repair_errors(mutator, code):
    flow = build_flow()
    mutator(flow)
    with pytest.raises(ValueError) as exc:
        validate_and_repair(flow, NODE_CATALOG)
    assert code in str(exc.value)
