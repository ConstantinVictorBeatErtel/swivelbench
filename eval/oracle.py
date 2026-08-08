"""Scripted perfect agent dispatcher for all domains.

  python3 eval/oracle.py --task CB-SEED-001
  python3 eval/oracle.py --task GR-SEED-001
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.registry import all_tasks, resolve  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="CB-SEED-001")
    a = ap.parse_args()
    domain = resolve(a.task)
    task = domain.tasks[a.task]
    work = Path(tempfile.mkdtemp(prefix="sb_oracle_"))
    pa, pb, assertions = domain.prepare(task, work)
    api = domain.make_api(pa, pb, task)
    domain.oracle_run(api)
    api.close()
    res = verifier.verify(pa, pb, assertions, domain=domain.name)
    print(f"oracle  task={task.task_id}  domain={domain.name}  "
          f"final={res.final:.3f}  raw={res.raw:.3f}")
    print("  by kind: " + "  ".join(
        f"{k}={v[0]:.1f}/{v[1]:.1f}" for k, v in sorted(res.by_kind.items())))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    return 0 if res.final == 1.0 else 1


if __name__ == "__main__":
    # Re-export FLAGS for adversarial suites that still do `from eval import oracle`
    from envs.commercial_banking import oracle as _cb  # noqa: F401
    from envs.grading import oracle as _gr  # noqa: F401
    sys.exit(main())


# Compatibility: adversarial tests may set oracle.FLAGS on this module while
# targeting a specific domain via domain.oracle_flags — prefer domain modules.
FLAGS: dict = {}
TASKS = all_tasks()
