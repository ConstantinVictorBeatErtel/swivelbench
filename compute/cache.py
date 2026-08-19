"""Content-addressed cache helpers used by OpenRouter and local workers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def request_key(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> str:
    payload = {"model": model, "messages": messages, "tools": tools or []}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class FileKVCache:
    """Tiny atomic disk KV cache for immutable pages, snapshots, and responses."""
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> bytes | None:
        path = self.root / key[:2] / key
        return path.read_bytes() if path.is_file() else None

    def put(self, key: str, value: bytes) -> Path:
        folder = self.root / key[:2]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / key
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(value)
        tmp.replace(path)
        return path
