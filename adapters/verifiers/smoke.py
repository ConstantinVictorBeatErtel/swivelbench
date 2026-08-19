"""Smoke-test helpers that do not require the verifiers package.

`python -m adapters.verifiers.smoke --task CB-SEED-001` builds a task, runs the
domain oracle through the same prepare/make_api path the Verifiers adapter uses,
and checks the authoritative all-criteria task_passed result.
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
from envs.registry import build_episode, resolve  # noqa: E402


def smoke(task_id: str, *, for_training: bool = True) -> bool:
    del for_training  # scoring no longer has a training/benchmark cliff
    domain = resolve(task_id)
    work = Path(tempfile.mkdtemp(prefix="sb_vf_smoke_"))
    try:
        episode = build_episode(task_id, work)
        api = episode.api
        if episode.step_id:
            if domain.name == "commercial_banking":
                from envs.commercial_banking.steps import run_one_request
                run_one_request(api, api.list_credit_requests()["requests"][0],
                                through_step=episode.step_id)
            else:
                from envs.grading.steps import run_through
                run_through(api, through_step=episode.step_id)
        else:
            domain.oracle_run(api)
        if domain.name == "teaching":
            from envs.teaching.scoring import score_session
            result = score_session(api)
            api.close()
            print(f"smoke task={task_id} domain=teaching "
                  f"score_100={result['score_100']:.3f} "
                  f"task_passed={result['task_passed']}")
            return result["task_passed"]
        api.close()
        res = verifier.verify(episode.pa, episode.pb, episode.assertions,
                              domain=domain.name,
                              artifacts_dir=episode.pa.parent / "artifacts",
                              step=episode.step_id)
        print(f"smoke task={task_id} domain={domain.name} "
              f"criterion_pass_rate={res.criterion_pass_rate:.3f} "
              f"task_passed={res.task_passed} "
              f"failed={res.failed or 'NONE'}")
        return res.task_passed
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="CB-SEED-001")
    ap.add_argument("--benchmark-cap", action="store_true",
                    help="(deprecated no-op) scoring no longer uses CRITICAL_CAP")
    a = ap.parse_args()
    passed = smoke(a.task)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
