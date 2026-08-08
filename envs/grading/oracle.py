"""Scripted perfect agent for grading."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import verifier  # noqa: E402
from envs.grading.actions import ActionAPI  # noqa: E402
from envs.grading.runtime import make_api, prepare  # noqa: E402
from envs.grading.task import SEED_TASK, TASKS  # noqa: E402

FLAGS: dict[str, bool] = {}


def F(k: str) -> bool:
    return bool(FLAGS.get(k))


def score_submission(sub: dict, items: list[dict]) -> dict[str, int]:
    answer = (sub.get("visible_answer") or "").lower()
    unclear = sub["clarity"] == "low" or sub["handwriting_noise"] == 1
    out = {}
    for it in items:
        key = it["expected_key"].lower()
        hit = key in answer
        if not hit:
            pts = 0
        elif unclear:
            pts = it["max_points"] // 2
        else:
            pts = it["max_points"]
        if F("full_credit_unclear") and unclear:
            pts = it["max_points"]
        out[it["item_key"]] = pts
    return out


def run(api: ActionAPI) -> None:
    from envs.grading.steps import run_through
    run_through(api)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=SEED_TASK.task_id)
    a = ap.parse_args()
    task = TASKS[a.task]
    work = Path(tempfile.mkdtemp(prefix="sb_gr_oracle_"))
    pa, pb, assertions = prepare(task, work)
    api = make_api(pa, pb, task)
    run(api)
    api.close()
    res = verifier.verify(pa, pb, assertions, domain="grading",
                          artifacts_dir=pa.parent / "artifacts")
    print(
        f"oracle  task={task.task_id}  "
        f"criterion_pass_rate={res.criterion_pass_rate:.3f}  "
        f"task_passed={res.task_passed}"
    )
    print("  by step: " + "  ".join(
        f"{k}={v:.2f}" for k, v in sorted(res.by_step.items())))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    sys.exit(0 if res.task_passed else 1)
