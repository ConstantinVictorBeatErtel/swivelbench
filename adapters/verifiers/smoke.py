"""Smoke-test helpers that do not require the verifiers package.

`python -m adapters.verifiers.smoke --task CB-SEED-001` builds a task, runs the
domain oracle through the same prepare/make_api path the Verifiers adapter uses,
and checks criterion_pass_rate == 1.0 / task_passed.
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
from envs.registry import prepare_for, resolve  # noqa: E402


def smoke(task_id: str, *, for_training: bool = True) -> float:
    del for_training  # scoring no longer has a training/benchmark cliff
    domain = resolve(task_id)
    work = Path(tempfile.mkdtemp(prefix="sb_vf_smoke_"))
    try:
        pa, pb, assertions, task = prepare_for(task_id, work)
        step_id = getattr(task, "step_id", None)
        parent_id = getattr(task, "parent_task_id", task_id)
        # make_api needs E2E Task knobs
        api_task = domain.tasks.get(parent_id, domain.seed_task)
        if "@" in str(parent_id):
            api_task = domain.seed_task
        from envs.commercial_banking.task import E2E_TASKS as CB_E2E
        from envs.grading.task import E2E_TASKS as GR_E2E
        if parent_id in CB_E2E:
            api_task = CB_E2E[parent_id]
        elif parent_id in GR_E2E:
            api_task = GR_E2E[parent_id]
        api = domain.make_api(pa, pb, api_task)
        if step_id:
            if domain.name == "commercial_banking":
                from envs.commercial_banking.steps import run_one_request
                run_one_request(api, api.list_credit_requests()["requests"][0],
                                through_step=step_id)
            else:
                from envs.grading.steps import run_through
                run_through(api, through_step=step_id)
        else:
            domain.oracle_run(api)
        api.close()
        res = verifier.verify(pa, pb, assertions,
                              domain=domain.name,
                              artifacts_dir=pa.parent / "artifacts",
                              step=step_id)
        print(f"smoke task={task_id} domain={domain.name} "
              f"criterion_pass_rate={res.criterion_pass_rate:.3f} "
              f"task_passed={res.task_passed} "
              f"failed={res.failed or 'NONE'}")
        return res.criterion_pass_rate
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="CB-SEED-001")
    ap.add_argument("--benchmark-cap", action="store_true",
                    help="(deprecated no-op) scoring no longer uses CRITICAL_CAP")
    a = ap.parse_args()
    score = smoke(a.task)
    sys.exit(0 if score == 1.0 else 1)


if __name__ == "__main__":
    main()
