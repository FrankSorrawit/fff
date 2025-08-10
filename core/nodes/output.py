from __future__ import annotations

from core.runtime.contracts import NodeContext


async def node_output(ctx: NodeContext):
    """Passthrough final payload to the caller."""

    return ctx.inputs
