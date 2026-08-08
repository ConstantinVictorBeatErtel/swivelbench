"""Base constrained typed surface. Domains subclass with their tools.

Design rule: this layer validates TYPES and EXISTENCE, not POLICY. Policy
mistakes are permitted here and caught by the verifier. Illegal writes return
a structured error rather than raising, so recovery behaviour is observable.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.db import ENV_NOW, attached


def ok(**kw: Any) -> dict:
    return {"ok": True, **kw}


def err(code: str, message: str, **kw: Any) -> dict:
    return {"ok": False, "error": {"code": code, "message": message, **kw}}


@dataclass
class BaseActionAPI:
    """Shared connection, tracing, and audit helpers for domain ActionAPIs."""

    path_a: Path
    path_b: Path
    action_codes: tuple[str, ...]
    actor: str = "agent"
    system_a_name: str = "system_a"
    system_b_name: str = "system_b"
    artifacts_dir: Path | None = None
    produced_files: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    _audit_seq: int = 0
    _appr_seq: int = 0

    def __post_init__(self) -> None:
        if not self.action_codes:
            raise ValueError("action_codes must be a non-empty controlled vocabulary")
        self.con = attached(self.path_a, self.path_b)
        self.con.row_factory = sqlite3.Row
        if self.artifacts_dir is not None:
            self.artifacts_dir = Path(self.artifacts_dir)
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _note_file(self, kind: str, path: Path, **meta: Any) -> str:
        rel = str(path)
        self.produced_files.append({"kind": kind, "path": rel, **meta})
        return rel

    def _rows(self, sql: str, args: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict | None:
        r = self.con.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _record(self, name: str, args: dict, result: dict) -> dict:
        self.trace.append({"action": name, "args": args, "ok": result["ok"],
                           "error": result.get("error", {}).get("code")})
        return result

    def log_action(self, actor: str, action: str, target_system: str,
                   target_key: str, note: str) -> dict:
        args = {"actor": actor, "action": action, "target_system": target_system,
                "target_key": target_key, "note": note}
        if target_system not in (self.system_a_name, self.system_b_name):
            return self._record("log_action", args, err(
                "invalid_value",
                f"target_system must be '{self.system_a_name}' or "
                f"'{self.system_b_name}'"))
        if action not in self.action_codes:
            return self._record("log_action", args, err(
                "invalid_value",
                f"action must be one of the controlled audit codes: "
                f"{', '.join(self.action_codes)}. Got {action!r}.",
                allowed=list(self.action_codes)))
        self._audit_seq += 1
        self.con.execute(
            "INSERT INTO b.audit_log VALUES (?,?,?,?,?,?,?)",
            (f"AL-{self._audit_seq:03d}", actor or self.actor, action,
             target_system, target_key, note, ENV_NOW))
        self.con.commit()
        return self._record("log_action", args,
                            ok(entry_id=f"AL-{self._audit_seq:03d}"))

    def request_approval(self, target: str, proposed_change: str,
                         rationale: str) -> dict:
        args = {"target": target, "proposed_change": proposed_change,
                "rationale": rationale}
        if not (target or "").strip():
            return self._record("request_approval", args, err(
                "invalid_value", "target must be a non-empty key reference"))
        target = target.strip()
        self._appr_seq += 1
        rid = f"AR-{self._appr_seq:03d}"
        self.con.execute(
            "INSERT INTO b.approval_requests VALUES (?,?,?,?,?)",
            (rid, target, proposed_change, rationale, ENV_NOW))
        self.con.commit()
        return self._record("request_approval", args,
                            ok(request_id=rid, status="pending_review"))

    def close(self) -> None:
        self.con.close()


# Backward-compatible alias while domains migrate off the old credit ActionAPI.
ActionAPI = BaseActionAPI
