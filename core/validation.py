from __future__ import annotations

from typing import Any, Dict

# JSON-like schema used for basic flow validation. This is not a full JSON
# Schema implementation but mirrors the important constraints from the design
# document.
FLOW_SPEC_SCHEMA: Dict[str, Any] = {
    "node_types": {
        "input",
        "rag.retrieve",
        "llm.chat",
        "email.read",
        "email.send",
        "calendar.create",
        "http.request",
        "code.exec",
        "output",
    }
}


def _apply_defaults_and_validate(params: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Apply defaults from ``schema`` to ``params`` and perform basic checks."""

    if not isinstance(params, dict):
        raise ValueError("PARAMS_NOT_OBJECT")

    result: Dict[str, Any] = {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in props.items():
        if name in params:
            value = params[name]
        elif "default" in prop:
            value = prop["default"]
        else:
            if name in required:
                raise ValueError(f"MISSING_PARAM:{name}")
            continue

        typ = prop.get("type")
        if typ == "string" and not isinstance(value, str):
            raise ValueError(f"INVALID_TYPE:{name}")
        if typ == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"INVALID_TYPE:{name}")
        if typ == "integer" and not isinstance(value, int):
            raise ValueError(f"INVALID_TYPE:{name}")
        if typ == "object" and not isinstance(value, dict):
            raise ValueError(f"INVALID_TYPE:{name}")
        if typ == "array" and not isinstance(value, list):
            raise ValueError(f"INVALID_TYPE:{name}")

        if isinstance(value, (int, float)):
            if "minimum" in prop and value < prop["minimum"]:
                raise ValueError(f"MIN_EXCEEDED:{name}")
            if "maximum" in prop and value > prop["maximum"]:
                raise ValueError(f"MAX_EXCEEDED:{name}")

        result[name] = value

    if not schema.get("additionalProperties", True):
        extras = set(params) - set(props)
        if extras:
            raise ValueError(f"UNKNOWN_PARAM:{extras.pop()}")

    return result


def validate_and_repair(flow: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ``flow`` structure and apply defaults using ``catalog``.

    The function performs a subset of the validation rules described in the
    specification: node id uniqueness, edge references, required first/last
    node types, and single in/out degree for each node. Parameters for each
    node are validated against the provided catalog and missing values are
    populated with defaults.
    """

    if not isinstance(flow, dict):
        raise ValueError("FLOW_NOT_OBJECT")

    if not isinstance(flow.get("name"), str) or not flow["name"]:
        raise ValueError("NAME_REQUIRED")

    nodes = flow.get("nodes")
    edges = flow.get("edges")
    if not isinstance(nodes, list) or len(nodes) < 2:
        raise ValueError("NODES_MIN_TWO")
    if not isinstance(edges, list) or len(edges) < 1:
        raise ValueError("EDGES_MIN_ONE")

    # Node id uniqueness and basic fields
    ids = []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("NODE_NOT_OBJECT")
        node_id = node.get("id")
        node_type = node.get("type")
        if not isinstance(node_id, str) or not node_id.startswith("n") or not node_id[1:].isdigit():
            raise ValueError("INVALID_NODE_ID")
        if node_id in ids:
            raise ValueError("DUPLICATE_NODE_ID")
        ids.append(node_id)
        if node_type not in FLOW_SPEC_SCHEMA["node_types"]:
            raise ValueError("UNKNOWN_NODE_TYPE")
        if "params" not in node:
            node["params"] = {}
        elif not isinstance(node["params"], dict):
            raise ValueError("PARAMS_NOT_OBJECT")

    node_lookup = {n["id"]: n for n in nodes}

    # Edge references
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("EDGE_NOT_OBJECT")
        src = edge.get("from")
        dst = edge.get("to")
        if src not in node_lookup or dst not in node_lookup:
            raise ValueError("EDGE_REF_INVALID")

    # First/last node types
    if nodes[0]["type"] != "input":
        raise ValueError("FIRST_NODE_MUST_BE_INPUT")
    if nodes[-1]["type"] != "output":
        raise ValueError("LAST_NODE_MUST_BE_OUTPUT")

    # Validate params with catalog and apply defaults
    for node in nodes:
        node_type = node["type"]
        schema = catalog["nodes"][node_type]["schema"]
        node["params"] = _apply_defaults_and_validate(node["params"], schema)

    # Topology check: single in/out
    deg_in = {nid: 0 for nid in node_lookup}
    deg_out = {nid: 0 for nid in node_lookup}
    for edge in edges:
        deg_out[edge["from"]] += 1
        deg_in[edge["to"]] += 1
    if any(v > 1 for v in deg_in.values()):
        raise ValueError("MULTI_IN_NOT_ALLOWED")
    if any(v > 1 for v in deg_out.values()):
        raise ValueError("MULTI_OUT_NOT_ALLOWED")

    return flow
