"""Database construction. Deterministic: same fixtures -> byte-identical DBs."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Environment-supplied frozen clock. Timestamps are never agent-supplied,
# otherwise assertions on tested_at become a clock race.
ENV_NOW = "2026-02-17T00:00:00Z"

# Not part of the two spec'd schemas: the escalation sink for request_approval.
APPROVALS_DDL = """
CREATE TABLE IF NOT EXISTS approval_requests (
  request_id      TEXT PRIMARY KEY,
  target          TEXT NOT NULL,
  proposed_change TEXT NOT NULL,
  rationale       TEXT,
  requested_at    TEXT NOT NULL
);
"""


def build(workdir: Path, *, fixtures: Path,
          name_a: str = "system_a.db", name_b: str = "system_b.db",
          seed_a: str = "seed_a.sql", seed_b: str = "seed_b.sql",
          ) -> tuple[Path, Path]:
    """Create system-A and system-B SQLite files from fixture SQL.

    `fixtures` is the domain package's fixture directory. The framework does
    not hard-code any domain path.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    path_a = workdir / name_a
    path_b = workdir / name_b
    for path, fixture in ((path_a, seed_a), (path_b, seed_b)):
        path.unlink(missing_ok=True)
        con = sqlite3.connect(path)
        con.executescript((fixtures / fixture).read_text())
        if fixture == seed_b:
            con.executescript(APPROVALS_DDL)
        con.commit()
        con.close()
    return path_a, path_b


def attached(path_a: Path, path_b: Path) -> sqlite3.Connection:
    """Open a connection with both systems ATTACHed as `a` and `b`.

    This is what makes a cross-system assertion a plain join.
    """
    con = sqlite3.connect(":memory:")
    con.execute("ATTACH ? AS a", (str(path_a),))
    con.execute("ATTACH ? AS b", (str(path_b),))
    return con
