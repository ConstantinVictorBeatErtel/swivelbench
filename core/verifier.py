"""Deterministic verifier. Reads final DB state, runs rubric criteria, scores.

Knows nothing about the agent, its transcript, or what it claimed to do.

Scoring (ComplexConstraints-style):
  - criterion_pass_rate = fraction of active criteria satisfied (dense RL reward)
  - task_passed = True iff every active criterion passes (published pass metric)

No raw/final split, no KIND_SHARE, no CRITICAL_CAP cliff.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from core.db import attached

# Hierarchy of Agentic Capabilities (CoreCraft / ComplexConstraints).
LEVELS = ("tool", "plan", "adapt", "ground", "reason")
LEVEL_LABELS = {
    "tool": "L1_tool_use",
    "plan": "L2_planning",
    "adapt": "L3_adaptability",
    "ground": "L4_groundedness",
    "reason": "L5_common_sense",
}
ROLES = ("required", "bonus", "penalty")

# Default within-kind weight when an assertion does not declare one.
WEIGHTS = {
    "positive": 1.0, "propagation": 1.0, "trail": 1.0, "negative": 1.0,
    "format": 1.0,
}


@dataclass
class Assertion:
    id: str
    kind: str
    weight: float
    sql: str
    step: str = ""
    level: str = "ground"
    role: str = "required"
    # Legacy alias kept only while migrating callers; ignored for scoring.
    critical: bool = False


@dataclass
class CriterionOutcome:
    id: str
    kind: str
    step: str
    level: str
    role: str
    passed: bool
    weight: float = 1.0
    title: str = ""
    why: str = ""
    detail: str = ""
    sql: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "step": self.step,
            "level": self.level, "role": self.role, "passed": self.passed,
            "weight": self.weight, "title": self.title, "why": self.why,
            "detail": self.detail, "sql": self.sql,
        }


@dataclass
class Result:
    criterion_pass_rate: float
    task_passed: bool
    passed: list[str]
    failed: list[str]
    criteria: list[CriterionOutcome] = field(default_factory=list)
    by_step: dict[str, float] = field(default_factory=dict)
    by_level: dict[str, float] = field(default_factory=dict)
    by_kind: dict[str, tuple[float, float]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    details: list[dict] | None = None

    # Backward-compat aliases so older callers keep working during migration.
    @property
    def raw(self) -> float:
        return self.criterion_pass_rate

    @property
    def final(self) -> float:
        return self.criterion_pass_rate

    @property
    def score_100(self) -> float:
        """0–100 benchmark score = criterion_pass_rate × 100."""
        return round(self.criterion_pass_rate * 100.0, 1)

    @property
    def critical_failed(self) -> list[str]:
        return [c.id for c in self.criteria
                if not c.passed and c.role == "penalty"]

    def as_dict(self) -> dict:
        out = {
            "criterion_pass_rate": self.criterion_pass_rate,
            "score_100": self.score_100,
            "task_passed": self.task_passed,
            "passed": self.passed,
            "failed": self.failed,
            "by_step": dict(self.by_step),
            "by_level": dict(self.by_level),
            "by_kind": {k: list(v) for k, v in self.by_kind.items()},
            "errors": self.errors,
            "criteria": [c.as_dict() for c in self.criteria],
            # Compat mirrors for older JSON consumers.
            "raw": self.criterion_pass_rate,
            "final": self.criterion_pass_rate,
            "critical_failed": self.critical_failed,
        }
        if self.details is not None:
            out["details"] = self.details
        return out


def load(path: Path) -> list[Assertion]:
    out: list[Assertion] = []
    meta, buf = None, []

    def flush() -> None:
        if meta and "\n".join(buf).strip():
            kind = meta["kind"]
            role = meta.get("role")
            if role is None:
                role = "penalty" if kind == "negative" else "required"
            level = meta.get("level", "ground")
            if level not in LEVELS:
                level = "ground"
            if role not in ROLES:
                role = "required"
            out.append(Assertion(
                id=meta["id"], kind=kind,
                weight=float(meta.get("weight", WEIGHTS.get(kind, 1.0))),
                critical=meta.get("critical") == "true",
                step=meta.get("step", ""),
                level=level,
                role=role,
                sql="\n".join(buf).strip().rstrip(";")))

    for line in path.read_text().splitlines():
        m = re.match(r"--\s*@assert\s+(.*)", line)
        if m:
            flush()
            meta = dict(p.split("=", 1) for p in m.group(1).split())
            buf = []
        elif meta is not None and not line.strip().startswith("--"):
            buf.append(line)
    flush()
    return out


def _rate(outcomes: list[CriterionOutcome]) -> float:
    if not outcomes:
        return 1.0
    return sum(1.0 for o in outcomes if o.passed) / len(outcomes)


def role_aware_reward(
    result: Result,
    *,
    alpha: float = 0.0,
    beta: float = 0.0,
) -> float:
    """ComplexConstraints Eq. 1: required + α·bonus − β·unmet_penalty."""
    req = [c for c in result.criteria if c.role == "required"]
    bonus = [c for c in result.criteria if c.role == "bonus"]
    pen = [c for c in result.criteria if c.role == "penalty"]
    r = _rate(req) if req else 0.0
    if bonus and alpha:
        r += alpha * _rate(bonus)
    if pen and beta:
        unmet = sum(1.0 for c in pen if not c.passed) / len(pen)
        r -= beta * unmet
    return round(max(0.0, min(1.0, r)), 4)


def verify(path_a: Path, path_b: Path, assertions_path: Path,
           critical_cap: float | None = None,  # noqa: ARG001 — ignored (compat)
           *, with_details: bool = False,
           artifacts_dir: Path | None = None,
           domain: str | None = None,
           step: str | None = None,
           assertion_ids: set[str] | None = None) -> Result:
    """Run rubric criteria. Optional step= / assertion_ids= filter for step episodes."""
    from core.format_check import check_domain

    del critical_cap  # scoring no longer uses a cliff

    con = attached(path_a, path_b)
    outcomes: list[CriterionOutcome] = []
    errors: dict[str, str] = {}
    by_kind: dict[str, list[float]] = {}

    for a in load(assertions_path):
        if step is not None and a.step and a.step != step:
            continue
        if assertion_ids is not None and a.id not in assertion_ids:
            continue
        try:
            row = con.execute(a.sql).fetchone()
            hit = bool(row and row[0])
        except sqlite3.Error as e:
            hit, errors[a.id] = False, str(e)
        k = by_kind.setdefault(a.kind, [0.0, 0.0])
        k[1] += a.weight
        if hit:
            k[0] += a.weight
        outcomes.append(CriterionOutcome(
            id=a.id, kind=a.kind, step=a.step, level=a.level, role=a.role,
            passed=hit, weight=a.weight, sql=a.sql,
        ))
    con.close()

    art = Path(artifacts_dir) if artifacts_dir is not None else (path_a.parent / "artifacts")
    if domain:
        for fc in check_domain(domain, art if art.is_dir() else None):
            if step is not None and fc.step and fc.step != step:
                continue
            if assertion_ids is not None and fc.id not in assertion_ids:
                continue
            k = by_kind.setdefault(fc.kind, [0.0, 0.0])
            k[1] += fc.weight
            if fc.passed:
                k[0] += fc.weight
            outcomes.append(CriterionOutcome(
                id=fc.id, kind=fc.kind, step=fc.step, level=fc.level,
                role=fc.role, passed=fc.passed, weight=fc.weight,
                title=fc.title, why=fc.why, detail=fc.detail,
            ))

    passed = [o.id for o in outcomes if o.passed]
    failed = [o.id for o in outcomes if not o.passed]
    rate = round(_rate(outcomes), 4)
    task_ok = len(failed) == 0 and len(outcomes) > 0

    by_step: dict[str, list[CriterionOutcome]] = defaultdict(list)
    by_level: dict[str, list[CriterionOutcome]] = defaultdict(list)
    for o in outcomes:
        if o.step:
            by_step[o.step].append(o)
        by_level[LEVEL_LABELS.get(o.level, o.level)].append(o)

    details = [o.as_dict() for o in outcomes] if with_details else None
    return Result(
        criterion_pass_rate=rate,
        task_passed=task_ok,
        passed=passed,
        failed=failed,
        criteria=outcomes,
        by_step={s: round(_rate(v), 4) for s, v in sorted(by_step.items())},
        by_level={lv: round(_rate(v), 4) for lv, v in sorted(by_level.items())},
        by_kind={k: (v[0], v[1]) for k, v in by_kind.items()},
        errors=errors,
        details=details,
    )
