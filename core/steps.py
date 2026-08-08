"""Shared multi-step episode primitives (Track A training units)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class StepSpec:
    """One self-contained workflow step: fair prompt, no prior transcript."""
    step_id: str
    title: str
    prompt: str
    max_steps: int = 40
    tool_allowlist: tuple[str, ...] = ()
    # Ordered prefix of oracle step fns to run before the agent acts.
    # The agent's step itself is NOT run by the oracle during prepare.
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StepTask:
    """A Task-like object for a single workflow step on a parent E2E seed."""
    task_id: str
    parent_task_id: str
    step_id: str
    level: int
    seed: int
    prompt: str
    assertions: Path
    max_steps: int
    domain: str
    use_bundled_fixtures: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)
    # Domain-specific knobs forwarded to prepare/make_api:
    requests: int = 1
    deal_limit_floor: float = 0.0
    inject_spread_errors: bool = True
    submissions: int = 3
    tool_allowlist: tuple[str, ...] = ()


def snapshot_copy(src_a: Path, src_b: Path, src_art: Path | None,
                  dest_dir: Path) -> tuple[Path, Path, Path | None]:
    """Copy DB (+ optional artifacts) into dest_dir for a fresh step episode."""
    import shutil
    dest_dir.mkdir(parents=True, exist_ok=True)
    pa = dest_dir / src_a.name
    pb = dest_dir / src_b.name
    shutil.copy2(src_a, pa)
    shutil.copy2(src_b, pb)
    art_out = None
    if src_art and src_art.is_dir():
        art_out = dest_dir / "artifacts"
        if art_out.exists():
            shutil.rmtree(art_out)
        shutil.copytree(src_art, art_out)
    return pa, pb, art_out
