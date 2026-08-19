"""Scripted perfect agent dispatcher for all domains.

  python3 eval/oracle.py --task CB-SEED-001
  python3 eval/oracle.py --task GR-SEED-001
  python3 eval/oracle.py --task CB-SEED-001@S3_model
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.registry import all_tasks, prepare_for, resolve  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="CB-SEED-001")
    a = ap.parse_args()
    domain = resolve(a.task)
    work = Path(tempfile.mkdtemp(prefix="sb_oracle_"))
    pa, pb, assertions, task = prepare_for(a.task, work)
    step_id = getattr(task, "step_id", None)
    parent_id = getattr(task, "parent_task_id", a.task)
    from envs.commercial_banking.task import E2E_TASKS as CB_E2E
    from envs.grading.task import E2E_TASKS as GR_E2E
    if parent_id in CB_E2E:
        api_task = CB_E2E[parent_id]
    elif parent_id in GR_E2E:
        api_task = GR_E2E[parent_id]
    else:
        api_task = domain.seed_task
    api = domain.make_api(pa, pb, api_task)
    if step_id:
        # prepare_for already ran the prefix; run only this step
        if domain.name == "commercial_banking":
            from envs.commercial_banking.steps import (
                run_one_request,
            )
            # Re-prepare without prefix then through_step is simpler for oracle CLI
            api.close()
            import shutil
            shutil.rmtree(work, ignore_errors=True)
            work = Path(tempfile.mkdtemp(prefix="sb_oracle_"))
            pa, pb, assertions = domain.prepare(api_task, work)
            api = domain.make_api(pa, pb, api_task)
            run_one_request(api, api.list_credit_requests()["requests"][0],
                            through_step=step_id)
        else:
            from envs.grading.steps import run_through
            api.close()
            import shutil
            shutil.rmtree(work, ignore_errors=True)
            work = Path(tempfile.mkdtemp(prefix="sb_oracle_"))
            pa, pb, assertions = domain.prepare(api_task, work)
            api = domain.make_api(pa, pb, api_task)
            run_through(api, through_step=step_id)
    else:
        domain.oracle_run(api)
    if domain.name == "teaching":
        from envs.teaching.scoring import score_session
        result = score_session(api)
        api.close()
        print(f"oracle  task={a.task}  domain=teaching "
              f"score_100={result['score_100']:.3f} "
              f"task_passed={result['task_passed']}")
        return 0 if result["task_passed"] else 1
    api.close()
    res = verifier.verify(pa, pb, assertions, domain=domain.name,
                          artifacts_dir=pa.parent / "artifacts",
                          step=step_id)
    print(f"oracle  task={a.task}  domain={domain.name}  "
          f"criterion_pass_rate={res.criterion_pass_rate:.3f}  "
          f"task_passed={res.task_passed}")
    print("  by step: " + ("  ".join(
        f"{k}={v:.2f}" for k, v in sorted(res.by_step.items())) or "(none)"))
    print("  by level: " + ("  ".join(
        f"{k}={v:.2f}" for k, v in sorted(res.by_level.items())) or "(none)"))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    return 0 if res.task_passed else 1


if __name__ == "__main__":
    from envs.commercial_banking import oracle as _cb  # noqa: F401
    from envs.grading import oracle as _gr  # noqa: F401
    sys.exit(main())


FLAGS: dict = {}
TASKS = all_tasks()
