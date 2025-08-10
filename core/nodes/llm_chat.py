from __future__ import annotations

import asyncio
import json
from urllib import request

from core.runtime.contracts import NodeContext

LITELLM_URL = "http://localhost:4000/v1/chat/completions"


async def node_llm_chat(ctx: NodeContext):
    """Call the LiteLLM gateway to get a chat completion using standard library."""

    body = {
        "model": ctx.params.get("model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": ctx.params.get("system", "Answer concisely.")},
            {
                "role": "user",
                "content": ctx.inputs.get("message")
                if isinstance(ctx.inputs, dict)
                else str(ctx.inputs),
            },
        ],
        "temperature": ctx.params.get("temperature", 0.2),
    }
    ctx.logger("calling litellm...")

    def _call():
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            LITELLM_URL, data=data, headers={"Content-Type": "application/json"}
        )
        with request.urlopen(req, timeout=ctx.timeout_ms / 1000) as resp:
            return json.loads(resp.read())

    data = await asyncio.to_thread(_call)
    text = data["choices"][0]["message"]["content"]
    return {"text": text, "raw": data}
