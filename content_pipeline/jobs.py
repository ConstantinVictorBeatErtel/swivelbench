"""Resumable, idempotent generation job records."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JOB_STATES = (
    "research_pending", "researched", "blueprint_approved", "generated",
    "solved", "reviewed", "rendered", "validated", "accepted", "quarantined",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class GenerationJob:
    job_id: str
    kind: str
    model_tier: str
    prompt_hash: str
    inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    seed: int = 0
    state: str = "research_pending"
    attempts: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    output_refs: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.state not in JOB_STATES:
            raise ValueError(f"unknown job state: {self.state}")

    def transition(self, state: str, *, issue: str | None = None) -> None:
        if state not in JOB_STATES:
            raise ValueError(f"unknown job state: {state}")
        self.state = state
        self.updated_at = utc_now()
        if issue:
            self.blocking_issues.append(issue)

    def record_attempt(self, *, output_refs: list[str] | None = None,
                       token_usage: dict[str, int] | None = None,
                       cost_usd: float = 0.0) -> None:
        self.attempts += 1
        self.updated_at = utc_now()
        if output_refs:
            self.output_refs = list(output_refs)
        if token_usage:
            self.token_usage = dict(token_usage)
        self.cost_usd += float(cost_usd)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "swivelbench.generation-job.v1", **asdict(self)}


class JobStore:
    """JSONL-backed job store with one canonical record per job ID."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _rows(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        rows: dict[str, dict[str, Any]] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["job_id"]] = row
        return rows

    def get(self, job_id: str) -> GenerationJob | None:
        row = self._rows().get(job_id)
        return GenerationJob(**{k: v for k, v in row.items() if k != "schema"}) if row else None

    def put(self, job: GenerationJob) -> None:
        rows = self._rows()
        rows[job.job_id] = job.to_dict()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text("".join(
            json.dumps(rows[k], sort_keys=True, ensure_ascii=False) + "\n"
            for k in sorted(rows)
        ), encoding="utf-8")
        tmp.replace(self.path)

    def list(self, *, state: str | None = None) -> list[GenerationJob]:
        jobs = [GenerationJob(**{k: v for k, v in row.items() if k != "schema"})
                for row in self._rows().values()]
        return sorted((j for j in jobs if state is None or j.state == state),
                      key=lambda j: j.job_id)
