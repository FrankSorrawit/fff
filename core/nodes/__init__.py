"""Collection of built-in node handlers for the prototype runtime.

This module exposes a mapping between node ``type`` strings used in a
``FlowSpec`` and the coroutine implementing the node's behaviour.  Tests use
``NODE_HANDLERS`` to execute small flows end‑to‑end, so any new node handler
should be added here.
"""

from .input import node_input
from .output import node_output
from .llm_chat import node_llm_chat
from .rag_retrieve import node_rag_retrieve

NODE_HANDLERS = {
    "input": node_input,
    "output": node_output,
    "llm.chat": node_llm_chat,
    "rag.retrieve": node_rag_retrieve,
}

__all__ = [
    "node_input",
    "node_output",
    "node_llm_chat",
    "node_rag_retrieve",
    "NODE_HANDLERS",
]
