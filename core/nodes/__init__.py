from .input import node_input
from .output import node_output
from .llm_chat import node_llm_chat

NODE_HANDLERS = {
    "input": node_input,
    "output": node_output,
    "llm.chat": node_llm_chat,
}

__all__ = ["node_input", "node_output", "node_llm_chat", "NODE_HANDLERS"]
