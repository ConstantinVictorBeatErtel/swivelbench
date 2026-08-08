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
from envs.grading.tools import SYSTEM_A, SYSTEM_B  # noqa: E402

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
    emails = api.list_emails()["emails"]
    # Prefer latest email unless adversarial flag
    ordered = sorted(emails, key=lambda e: e["sent_at"], reverse=True)
    if F("use_messy_email"):
        win = max(emails, key=lambda e: e["is_messy"])
    else:
        win = ordered[0]
    detail = api.get_email(win["email_id"])
    drafts = detail["rubric_drafts"]
    items = [{
        "item_key": d["item_key"],
        "description": d["description"],
        "max_points": d["max_points"],
        "expected_key": d["expected_key"],
        "item_ord": d["item_ord"],
    } for d in drafts]

    assignments = api.list_assignments()["assignments"]
    asn = next(a for a in assignments if a["code"] == win["assignment_code"])
    api.publish_rubric(asn["assignment_id"], win["email_id"], items)
    api.log_action("ta_agent", "publish_rubric", SYSTEM_B, asn["assignment_id"],
                   f"From {win['email_id']}; total={sum(i['max_points'] for i in items)}")

    rubric = api.get_rubric(asn["assignment_id"])
    ritems = rubric["items"]

    api.list_submissions(asn["assignment_id"])
    api.log_action("ta_agent", "open_submissions", SYSTEM_B,
                   asn["assignment_id"], "Opened Gradescope submissions")

    for s in api.list_submissions(asn["assignment_id"])["submissions"]:
        sub = api.get_submission(s["submission_id"])["submission"]
        user_id = sub["user_id"]
        if F("wrong_student") and user_id == "U-100":
            user_id = "U-101"
        scores = score_submission(sub, ritems)
        api.set_item_scores(sub["submission_id"], user_id, scores,
                            comment=f"clarity={sub['clarity']}")
        api.log_action("ta_agent", "grade_item", SYSTEM_B, sub["submission_id"],
                       f"scored {scores}")

    for rg in api.list_regrade_requests("open")["requests"]:
        if F("skip_regrades"):
            continue
        if rg["claim_type"] == "out_of_rubric":
            if F("grant_bait"):
                api.resolve_regrade(rg["regrade_id"], "adjust",
                                    "granted creativity", adjusted_total=10)
            else:
                api.resolve_regrade(rg["regrade_id"], "uphold",
                                    "Claim outside rubric; upheld")
            api.log_action("ta_agent", "resolve_regrade", SYSTEM_B,
                           rg["regrade_id"], rg["claim_type"])
        elif rg["claim_type"] == "arithmetic":
            g = api.get_grade(rg["submission_id"])
            if g["ok"]:
                summed = sum(i["points"] for i in g["items"])
                if summed != g["grade"]["grade_total"]:
                    api.resolve_regrade(rg["regrade_id"], "adjust",
                                        "Fixed arithmetic",
                                        adjusted_total=summed)
                else:
                    api.resolve_regrade(rg["regrade_id"], "uphold",
                                        "Totals already consistent")
            else:
                api.resolve_regrade(rg["regrade_id"], "uphold", "No grade found")
            api.log_action("ta_agent", "resolve_regrade", SYSTEM_B,
                           rg["regrade_id"], "arithmetic")
        else:
            api.resolve_regrade(rg["regrade_id"], "uphold", "Default uphold")
            api.log_action("ta_agent", "resolve_regrade", SYSTEM_B,
                           rg["regrade_id"], rg["claim_type"])


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
    print(f"oracle  task={task.task_id}  final={res.final:.3f}  raw={res.raw:.3f}")
    print("  by kind: " + "  ".join(
        f"{k}={v[0]:.1f}/{v[1]:.1f}" for k, v in sorted(res.by_kind.items())))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    sys.exit(0 if res.final == 1.0 else 1)
