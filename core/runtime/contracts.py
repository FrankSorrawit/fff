from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict


class NodeContext:
    """Execution context passed to each node handler.

    Attributes:
        run_id: Identifier of the current run.
        node_id: Identifier of the node being executed.
        inputs: Payload from the previous node.
        params: Parameters for this node.
        secrets: Mapping of secret values.
        user: User information dict including roles.
        logger: Callable used to log debug information.
        emit: Callable used to stream events back to the runtime.
        timeout_ms: Maximum time allowed for the node to run in milliseconds.
    """

    def __init__(
        self,
        run_id: str,
        node_id: str,
        inputs: Any,
        params: Dict[str, Any],
        secrets: Dict[str, str],
        user: Dict[str, Any],
        logger: Callable[[str], None],
        emit: Callable[[Dict[str, Any]], None],
        timeout_ms: int,
    ) -> None:
        self.run_id = run_id
        self.node_id = node_id
        self.inputs = inputs
        self.params = params
        self.secrets = secrets
        self.user = user
        self.logger = logger
        self.emit = emit
        self.timeout_ms = timeout_ms


NodeHandler = Callable[[NodeContext], Awaitable[Any]]
