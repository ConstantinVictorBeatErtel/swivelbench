"""Smoke-test helpers that do not require the verifiers package.

`python -m adapters.verifiers.smoke --task CB-SEED-001` builds a task, runs the
domain oracle through the same prepare/make_api path the Verifiers adapter uses,
and checks the reward is 1.0.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import verifier  # noqa: E402
from envs.registry import resolve  # noqa: E402


def smoke(task_id: str, *, for_training: bool = True) -> float:
    domain = resolve(task_id)
    task = domain.tasks[task_id]
    work = Path(tempfile.mkdtemp(prefix="sb_vf_smoke_"))
    try:
        pa, pb, assertions = domain.prepare(task, work)
        api = domain.make_api(pa, pb, task)
        domain.oracle_run(api)
        api.close()
        cap = None if for_training else verifier.CRITICAL_CAP
        res = verifier.verify(pa, pb, assertions, critical_cap=cap,
                              domain=domain.name,
                              artifacts_dir=pa.parent / "artifacts")
        print(f"smoke task={task_id} domain={domain.name} "
              f"final={res.final:.3f} raw={res.raw:.3f} "
              f"cap={cap} failed={res.failed or 'NONE'}")
        return res.final
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="CB-SEED-001")
    ap.add_argument("--benchmark-cap", action="store_true",
                    help="use CRITICAL_CAP=0.30 instead of training weights-only")
    a = ap.parse_args()
    score = smoke(a.task, for_training=not a.benchmark_cap)
    sys.exit(0 if score == 1.0 else 1)


if __name__ == "__main__":
    main()
