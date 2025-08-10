from __future__ import annotations

from typing import Any, Dict

# Minimal node catalog used for validation in tests. Only a subset of the
# nodes from the full specification are implemented for the prototype.
NODE_CATALOG: Dict[str, Any] = {
    "version": 1,
    "nodes": {
        "input": {
            "schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        },
        "rag.retrieve": {
            "schema": {
                "type": "object",
                "properties": {
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 5,
                    },
                    "filters": {"type": "object", "default": {}},
                },
                "required": ["top_k"],
                "additionalProperties": False,
            }
        },
        "llm.chat": {
            "schema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": "gpt-4o-mini"},
                    "system": {"type": "string", "default": "Answer concisely."},
                    "temperature": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 2,
                        "default": 0.2,
                    },
                },
                "required": ["model"],
                "additionalProperties": False,
            }
        },
        "output": {
            "schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        },
    },
}
