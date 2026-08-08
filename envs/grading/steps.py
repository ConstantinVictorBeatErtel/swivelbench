"""Per-step grading prompts and oracle step runners (Track A)."""
from __future__ import annotations

from pathlib import Path

from core.steps import StepSpec, StepTask
from envs.grading.actions import ActionAPI
from envs.grading.oracle import F, score_submission
from envs.grading.runtime import make_api, prepare
from envs.grading.task import SEED_TASK, Task
from envs.grading.tools import SYSTEM_A, SYSTEM_B

STEP_SPECS: dict[str, StepSpec] = {
    "S1_rubric": StepSpec(
        step_id="S1_rubric",
        title="Publish rubric from professor email",
        max_steps=30,
        tool_allowlist=(
            "list_emails", "get_email", "list_assignments",
            "publish_rubric", "get_rubric", "log_action", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

Systems: inbox (A) and gradescope (B). No SQL. Use tools only.

Job (S1 — publish rubric):
  Read professor emails, prefer the latest consistent rubric (not the messy
  earlier draft), and publish it to Gradescope. Log publish_rubric.

Graded checklist:
  - P1/P2/X1/X3/X4: rubric from EM-02, total 10, two items matching drafts
  - N1: do not publish from EM-01
  - T1: audit publish_rubric

Call finish when done.
""",
    ),
    "S2_queue": StepSpec(
        step_id="S2_queue",
        title="Open Gradescope submissions",
        max_steps=20,
        tool_allowlist=(
            "list_assignments", "list_submissions", "get_submission",
            "list_students", "log_action", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

A rubric is already published.

Job (S2 — open queue):
  Open the assignment submissions list and log open_submissions for ASN-HW1.

Graded checklist:
  - T5: audit open_submissions for ASN-HW1

Call finish when done.
""",
    ),
    "S3_grade": StepSpec(
        step_id="S3_grade",
        title="Grade submissions + gradesheet",
        max_steps=60,
        tool_allowlist=(
            "list_assignments", "list_submissions", "get_submission",
            "get_rubric", "set_item_scores", "get_grade",
            "log_action", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

Rubric is published; submissions are available.

Job (S3 — grade):
  Grade each submission against the published rubric. Unclear / noisy answers
  get at most half points (floor int). Never grade the wrong student. Leave a
  real Gradescope gradesheet .docx. Log grade_item.

Graded checklist:
  - P3/P4/P5/P7/P8/P9: totals 10 / 2 / 0 with correct item facets; 3 grades
  - X2/X5: totals equal item sums; two items each
  - N2/N3: not wrong student on SUB-1; SUB-2 total not > 5
  - T2: audit grade_item
  - F1: real gradesheet .docx

Call finish when done.
""",
    ),
    "S4_regrades": StepSpec(
        step_id="S4_regrades",
        title="Resolve regrade requests",
        max_steps=30,
        tool_allowlist=(
            "list_regrade_requests", "get_grade", "resolve_regrade",
            "log_action", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

Grades are already entered.

Job (S4 — regrades):
  Process every open regrade. Out-of-rubric creativity claims are upheld
  (not adjusted). Arithmetic claims: adjust only if the sum is wrong.
  Log each resolve_regrade.

Graded checklist:
  - P6/P10: both requests closed and upheld
  - N4/N5: RG-1 not adjusted; none left open
  - T3/T4: audit resolve_regrade for RG-1 and RG-2

Call finish when done.
""",
    ),
}

STEP_ORDER = list(STEP_SPECS.keys())


def step_S1_rubric(api: ActionAPI, ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    emails = api.list_emails()["emails"]
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
    ctx["asn"] = asn
    ctx["items"] = items
    return ctx


def step_S2_queue(api: ActionAPI, ctx: dict) -> dict:
    asn = ctx["asn"]
    api.list_submissions(asn["assignment_id"])
    api.log_action("ta_agent", "open_submissions", SYSTEM_B,
                   asn["assignment_id"], "Opened Gradescope submissions")
    return ctx


def step_S3_grade(api: ActionAPI, ctx: dict) -> dict:
    asn = ctx["asn"]
    rubric = api.get_rubric(asn["assignment_id"])
    ritems = rubric["items"]
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
    return ctx


def step_S4_regrades(api: ActionAPI, ctx: dict) -> dict:
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
    return ctx


ORACLE_STEPS = {
    "S1_rubric": step_S1_rubric,
    "S2_queue": step_S2_queue,
    "S3_grade": step_S3_grade,
    "S4_regrades": step_S4_regrades,
}


def run_through(api: ActionAPI, through_step: str | None = None) -> dict:
    ctx: dict = {}
    for sid in STEP_ORDER:
        fn = ORACLE_STEPS[sid]
        ctx = fn(api, ctx) if sid != "S1_rubric" else fn(api)
        if through_step is not None and sid == through_step:
            break
    return ctx


def prepare_step_episode(task: Task, step_id: str, workdir: Path
                         ) -> tuple[Path, Path, Path]:
    if step_id not in STEP_SPECS:
        raise KeyError(step_id)
    idx = STEP_ORDER.index(step_id)
    prefix = STEP_ORDER[:idx]
    pa, pb, assertions = prepare(task, workdir)
    api = make_api(pa, pb, task)
    try:
        if prefix:
            run_through(api, through_step=prefix[-1])
    finally:
        api.close()
    return pa, pb, assertions


def make_step_tasks(parent: Task = SEED_TASK) -> dict[str, StepTask]:
    out: dict[str, StepTask] = {}
    for sid, spec in STEP_SPECS.items():
        tid = f"{parent.task_id}@{sid}"
        out[tid] = StepTask(
            task_id=tid,
            parent_task_id=parent.task_id,
            step_id=sid,
            level=parent.level,
            seed=parent.seed,
            prompt=spec.prompt,
            assertions=parent.assertions,
            max_steps=spec.max_steps,
            domain="grading",
            use_bundled_fixtures=parent.use_bundled_fixtures,
            tags=parent.tags + ("step", sid),
            submissions=parent.submissions,
            tool_allowlist=spec.tool_allowlist,
        )
    return out
