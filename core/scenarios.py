"""Shared deterministic scenario and artifact primitives.

The benchmark keeps the public task description separate from the hidden gold
manifest.  This module is intentionally dependency-free so generators and
verifiers can be used in training jobs, local tests, and RunPod workers.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def stable_seed(*parts: object) -> int:
    """Return a reproducible 64-bit seed for a tuple of scenario dimensions."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def content_hash(value: Any) -> str:
    """Hash JSON-able values canonically for cache keys and state snapshots."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def rng_for(*parts: object) -> random.Random:
    return random.Random(stable_seed(*parts))


@dataclass(frozen=True)
class ScenarioManifest:
    scenario_id: str
    domain: str
    split: str
    seed: int
    difficulty: str
    public: dict[str, Any]
    gold: dict[str, Any] = field(repr=False)
    variant_axes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    scorer_version: str = "1.0"

    @property
    def public_hash(self) -> str:
        return content_hash(self.public)

    def redacted(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("gold", None)
        data["public_hash"] = self.public_hash
        return data

    def write(self, root: Path) -> tuple[Path, Path]:
        """Write public and hidden manifests beneath ``root``."""
        root.mkdir(parents=True, exist_ok=True)
        public_path = root / f"{self.scenario_id}.json"
        gold_path = root / f"{self.scenario_id}.gold.json"
        public_path.write_text(json.dumps(self.redacted(), indent=2, sort_keys=True) + "\n")
        gold_path.write_text(json.dumps(self.gold, indent=2, sort_keys=True) + "\n")
        return public_path, gold_path


def load_manifest(public_path: Path, gold_path: Path | None = None) -> ScenarioManifest:
    data = json.loads(public_path.read_text())
    gold = json.loads(gold_path.read_text()) if gold_path else {}
    return ScenarioManifest(
        scenario_id=data["scenario_id"], domain=data["domain"],
        split=data["split"], seed=int(data["seed"]),
        difficulty=data["difficulty"], public=data["public"], gold=gold,
        variant_axes=data.get("variant_axes") or {},
        schema_version=data.get("schema_version", "1.0"),
        scorer_version=data.get("scorer_version", "1.0"),
    )
