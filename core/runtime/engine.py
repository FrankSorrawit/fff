from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, Optional

from .contracts import NodeContext, NodeHandler


async def run_flow(
    flow: Dict[str, Any],
    inputs: Any,
    handlers: Dict[str, NodeHandler],
    emit: Optional[Callable[[Dict[str, Any]], None]] = None,
    *,
    run_id: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
    secrets: Optional[Dict[str, str]] = None,
    logger: Optional[Callable[[str], None]] = None,
    timeout_ms: int = 30_000,
) -> Any:
    """Execute a flow sequentially.

    Parameters
    ----------
    flow: dict
        Flow specification containing ``nodes`` and ``edges`` arrays.
    inputs: any
        Initial payload supplied to the first node.
    handlers: dict
        Mapping of node ``type`` to async handler callable.
    emit: callable, optional
        Function used to emit step events. Defaults to no-op.
    run_id: str, optional
        Identifier for this run. Generated if not provided.
    user: dict, optional
        User information passed to each node context.
    secrets: dict, optional
        Secrets available to node handlers.
    logger: callable, optional
        Logger used for debugging.
    timeout_ms: int, optional
        Maximum time allotted for each node.
    """

    run_id = run_id or uuid.uuid4().hex
    emit = emit or (lambda evt: None)
    logger = logger or (lambda msg: None)
    user = user or {}
    secrets = secrets or {}

    nodes = {n["id"]: n for n in flow.get("nodes", [])}
    edges = {e["from"]: e["to"] for e in flow.get("edges", [])}

    current_id = flow["nodes"][0]["id"] if flow.get("nodes") else None
    payload = inputs

    while current_id:
        node = nodes[current_id]
        handler = handlers.get(node["type"])
        if handler is None:
            raise KeyError(f"No handler for node type {node['type']}")

        ctx = NodeContext(
            run_id=run_id,
            node_id=current_id,
            inputs=payload,
            params=node.get("params", {}),
            secrets=secrets,
            user=user,
            logger=lambda m, nid=current_id: logger(f"[{nid}] {m}"),
            emit=emit,
            timeout_ms=timeout_ms,
        )

        emit({"type": "step_started", "node_id": current_id})
        start = time.perf_counter()
        try:
            payload = await handler(ctx)
        except Exception as exc:  # pragma: no cover - failure path
            latency = int((time.perf_counter() - start) * 1000)
            emit(
                {
                    "type": "step_failed",
                    "node_id": current_id,
                    "latency_ms": latency,
                    "error": str(exc),
                }
            )
            raise
        latency = int((time.perf_counter() - start) * 1000)
        emit({"type": "step_succeeded", "node_id": current_id, "latency_ms": latency})

        current_id = edges.get(current_id)

    return payload
