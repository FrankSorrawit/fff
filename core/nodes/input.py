from __future__ import annotations

from core.runtime.contracts import NodeContext


async def node_input(ctx: NodeContext):
    """Return the initial payload provided to the flow.

    For the prototype the input node simply forwards its inputs
    unchanged so downstream nodes receive the provided payload.
    """

    return ctx.inputs
