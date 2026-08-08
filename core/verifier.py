"""Deterministic verifier. Reads the final DB state, runs literal SQL, scores.

Knows nothing about the agent, its trace, or what it claimed to do.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.db import attached

# One config dict. Documented in the README, trivially changeable.
#
# Each KIND contributes a FIXED share of the reward, and assertions split their
# kind's share according to their own weights. This matters: with raw additive
# weights, adding a new trap silently reweights the whole benchmark -- the
# negative class drifted to 46% of total weight simply because traps are easy
# to add. Normalising by kind makes "add a task" and "change what the reward
# values" independent decisions.
KIND_SHARE = {
    "positive": 0.18,
    "propagation": 0.27,
    "negative": 0.32,
    "trail": 0.13,
    "format": 0.10,
}

# Default within-kind weight when an assertion does not declare one.
WEIGHTS = {"positive": 1.0, "propagation": 1.0, "trail": 1.0, "negative": 1.0,
           "format": 1.0}

# A weighted fraction cannot express "disqualifying". Assertions tagged
# critical=true cap the reward when they fail. Set to None for weights-only
# scoring (recommended for RL training, where the cliff hurts advantage
# estimation); keep it for the reported benchmark number.
CRITICAL_CAP: float | None = 0.30


@dataclass
class Assertion:
    id: str
    kind: str
    weight: float
    critical: bool
    sql: str


@dataclass
class Result:
    raw: float
    final: float
    passed: list[str]
    failed: list[str]
    critical_failed: list[str]
    by_kind: dict[str, tuple[float, float]]
    errors: dict[str, str]
    details: list[dict] | None = None

    def as_dict(self) -> dict:
        out = {"raw": self.raw, "final": self.final,
               "passed": self.passed, "failed": self.failed,
               "critical_failed": self.critical_failed,
               "by_kind": {k: list(v) for k, v in self.by_kind.items()},
               "errors": self.errors}
        if self.details is not None:
            out["details"] = self.details
        return out


def load(path: Path) -> list[Assertion]:
    out: list[Assertion] = []
    meta, buf = None, []

    def flush() -> None:
        if meta and "\n".join(buf).strip():
            out.append(Assertion(
                id=meta["id"], kind=meta["kind"],
                weight=float(meta.get("weight", WEIGHTS[meta["kind"]])),
                critical=meta.get("critical") == "true",
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


def verify(path_a: Path, path_b: Path, assertions_path: Path,
           critical_cap: float | None = CRITICAL_CAP,
           *, with_details: bool = False,
           artifacts_dir: Path | None = None,
           domain: str | None = None) -> Result:
    from core.format_check import check_domain

    con = attached(path_a, path_b)
    passed, failed, crit, errors = [], [], [], {}
    details: list[dict] = []
    by_kind: dict[str, list[float]] = {}
    for a in load(assertions_path):
        try:
            row = con.execute(a.sql).fetchone()
            hit = bool(row and row[0])
        except sqlite3.Error as e:
            hit, errors[a.id] = False, str(e)
        k = by_kind.setdefault(a.kind, [0.0, 0.0])
        k[1] += a.weight
        if hit:
            k[0] += a.weight
            passed.append(a.id)
        else:
            failed.append(a.id)
            if a.critical:
                crit.append(a.id)
        if with_details:
            details.append({
                "id": a.id, "kind": a.kind, "weight": a.weight,
                "critical": a.critical, "passed": hit, "sql": a.sql,
            })
    con.close()

    art = Path(artifacts_dir) if artifacts_dir is not None else (path_a.parent / "artifacts")
    if domain:
        for fc in check_domain(domain, art if art.is_dir() else None):
            k = by_kind.setdefault(fc.kind, [0.0, 0.0])
            k[1] += fc.weight
            if fc.passed:
                k[0] += fc.weight
                passed.append(fc.id)
            else:
                failed.append(fc.id)
                if fc.critical:
                    crit.append(fc.id)
            if with_details:
                details.append({
                    "id": fc.id, "kind": fc.kind, "weight": fc.weight,
                    "critical": fc.critical, "passed": fc.passed,
                    "title": fc.title, "why": fc.why, "detail": fc.detail,
                    "sql": "",
                })

    raw = sum(KIND_SHARE.get(k, 0.0) * (v[0] / v[1])
              for k, v in by_kind.items() if v[1]) / \
        sum(KIND_SHARE.get(k, 0.0) for k, v in by_kind.items() if v[1])
    final = min(raw, critical_cap) if (crit and critical_cap is not None) else raw
    return Result(raw=round(raw, 4), final=round(final, 4), passed=passed,
                  failed=failed, critical_failed=crit,
                  by_kind={k: (v[0], v[1]) for k, v in by_kind.items()},
                  errors=errors,
                  details=details if with_details else None)
