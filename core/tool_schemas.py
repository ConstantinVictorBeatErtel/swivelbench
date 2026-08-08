"""OpenAI-compatible tool schema helpers. Framework-agnostic.

Domain packages build their own tool lists with `_t` / `S` / `N` / `I`.
The framework never imports a domain package.
"""
from __future__ import annotations


def tool(name: str, desc: str, props: dict, required: list[str]) -> dict:
    """Build one OpenAI function-calling tool schema."""
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props,
                       "required": required, "additionalProperties": False}}}


# Short aliases used throughout domain packages.
_t = tool
S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}
