"""Per-step grading prompts and oracle step runners (Track A)."""
from __future__ import annotations

from pathlib import Path

from core.steps import StepSpec, StepTask
from envs.grading.actions import ActionAPI
from envs.grading.oracle import F, score_submission
from envs.grading.policy import POLICY_TEXT
from envs.grading.runtime import make_api, prepare
from envs.grading.task import SEED_TASK, Task
from envs.grading.tools import SYSTEM_B

STEP_SPECS: dict[str, StepSpec] = {
    "S1_rubric": StepSpec(
        step_id="S1_rubric",
        title="Publish rubric from professor email",
        max_steps=30,
        tool_allowlist=(
            "list_emails", "get_email", "list_assignments",
            "publish_rubric", "get_rubric", "log_action",
            "request_approval", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

Systems: inbox (A) and gradescope (B). No SQL. Use tools only.

Job (S1 — publish rubric):
  Read the professor's emails and any linked rubric drafts, reconcile them
  per the policy below, and publish the correct rubric to Gradescope.

You are graded on:
  - publishing the rubric the professor actually intended — the right items,
    right point values, right total — not a superseded or non-authoritative
    draft
  - not publishing a rubric that disagrees with the winning email's stated
    total; escalate instead of guessing if the drafts don't add up
  - leaving an audit entry for the publish

{policy}

Call finish when done.
""".format(policy=POLICY_TEXT),
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
  Open the assignment's Gradescope submission queue.

You are graded on:
  - leaving an audit entry that the queue was opened

For context, the full grading POLICY (not needed for this step, but shown
for consistency across the workflow):

{policy}

Call finish when done.
""".format(policy=POLICY_TEXT),
    ),
    "S3_grade": StepSpec(
        step_id="S3_grade",
        title="Grade submissions + gradesheet",
        max_steps=60,
        tool_allowlist=(
            "list_assignments", "list_submissions", "get_submission",
            "list_students", "get_rubric", "set_item_scores",
            "export_gradesheet", "get_grade", "log_action",
            "request_approval", "finish",
        ),
        prompt="""\
You are a course TA. THIS EPISODE IS ONE STEP ONLY.

Rubric is published; submissions are available.

Job (S3 — grade):
  Grade every submission that should be graded this episode, following the
  policy below exactly, then export a real Gradescope gradesheet.

You are graded on:
  - scoring every gradable submission exactly per the policy's matching and
    clarity rules — not close, exact
  - never grading a submission onto the wrong student
  - recognizing submissions that must be escalated instead of guessed (e.g.
    an unrecognized user_id, or a superseded resubmission), and not grading
    those
  - each recorded total actually equalling the sum of its item scores
  - an audit entry for every grade you write
  - a real, current gradesheet export whose totals match the final grades —
    export again if a later step in this workflow changes a grade

{policy}

Call finish when done.
""".format(policy=POLICY_TEXT),
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
  Resolve every open regrade request per the policy below.

You are graded on:
  - resolving each regrade exactly as the policy dictates for its claim
    type — a creativity claim outside the rubric is not the same as a
    genuine arithmetic error, and neither should be guessed
  - never re-touching a regrade that was already resolved before this
    episode started
  - when you do adjust a regrade, leaving item scores and the total
    consistent with each other
  - none left unresolved, and an audit entry for every resolution

{policy}

Call finish when done.
""".format(policy=POLICY_TEXT),
    ),
}

STEP_ORDER = list(STEP_SPECS.keys())


PROF_SENDER = "prof@university.edu"


def step_S1_rubric(api: ActionAPI, ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    emails = api.list_emails()["emails"]
    prof_emails = [e for e in emails if e["sender"] == PROF_SENDER]
    ordered = sorted(prof_emails, key=lambda e: e["sent_at"], reverse=True)
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
    ctx["asn"] = asn
    total = sum(i["max_points"] for i in items)
    if not F("use_messy_email") and (not items or total != win["stated_total_points"]):
        api.request_approval(
            asn["assignment_id"],
            f"rubric drafts for {win['email_id']} sum to {total}, but the "
            f"email states total {win['stated_total_points']}",
            "Drafts do not sum to the stated total; withholding publish "
            "until reconciled rather than guessing.")
        ctx["items"] = None
        return ctx
    api.publish_rubric(asn["assignment_id"], win["email_id"], items)
    api.log_action("ta_agent", "publish_rubric", SYSTEM_B, asn["assignment_id"],
                   f"From {win['email_id']}; total={total}")
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
    if not rubric["ok"]:
        return ctx  # S1 escalated instead of publishing; nothing to grade
    ritems = rubric["items"]
    students = {s["user_id"] for s in api.list_students()["students"]}
    subs = api.list_submissions(asn["assignment_id"])["submissions"]

    by_user: dict[str, list[str]] = {}
    for s in subs:
        by_user.setdefault(s["user_id"], []).append(s["submission_id"])
    superseded = {sid for sids in by_user.values() if len(sids) > 1
                 for sid in sorted(sids)[:-1]}

    for s in subs:
        sid = s["submission_id"]
        if sid in superseded:
            continue  # an earlier submission superseded by a resubmission
        if api.get_grade(sid)["ok"]:
            continue  # already graded (e.g. by a previous TA) — only a
                      # regrade request corrects that, not a fresh S3 grade
        sub = api.get_submission(sid)["submission"]
        user_id = sub["user_id"]
        if F("wrong_student") and user_id == "U-100":
            user_id = "U-101"
        if user_id not in students:
            api.request_approval(
                sid, f"submission {sid} references unknown user_id {user_id!r}",
                "user_id is not in the Gradescope roster; will not guess "
                "an identity.")
            continue
        scores = score_submission(sub, ritems)
        api.set_item_scores(sid, user_id, scores, comment=f"clarity={sub['clarity']}")
        api.log_action("ta_agent", "grade_item", SYSTEM_B, sid, f"scored {scores}")
    api.export_gradesheet(asn["assignment_id"])
    return ctx


def step_S4_regrades(api: ActionAPI, ctx: dict) -> dict:
    adjusted_any = False
    for rg in api.list_regrade_requests("open")["requests"]:
        if F("skip_regrades"):
            continue
        if rg["claim_type"] == "out_of_rubric":
            if F("grant_bait"):
                g = api.get_grade(rg["submission_id"])
                items = ({i["item_key"]: i["points"] for i in g["items"]}
                        if g["ok"] else {})
                items = {k: max(v, 5) for k, v in items.items()} or {"Q1": 5}
                api.resolve_regrade(rg["regrade_id"], "adjust",
                                    "granted creativity", item_scores=items)
                adjusted_any = True
            else:
                api.resolve_regrade(rg["regrade_id"], "uphold",
                                    "Claim outside rubric; upheld")
            api.log_action("ta_agent", "resolve_regrade", SYSTEM_B,
                           rg["regrade_id"], rg["claim_type"])
        elif rg["claim_type"] == "arithmetic":
            g = api.get_grade(rg["submission_id"])
            if g["ok"]:
                items = {i["item_key"]: i["points"] for i in g["items"]}
                summed = sum(items.values())
                if summed != g["grade"]["grade_total"]:
                    api.resolve_regrade(rg["regrade_id"], "adjust",
                                        "Fixed arithmetic", item_scores=items)
                    adjusted_any = True
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
    if adjusted_any and ctx.get("asn"):
        # A regrade changed a grade_total after S3 already exported the
        # gradesheet — re-export so the .docx isn't stale (P7/F2).
        api.export_gradesheet(ctx["asn"]["assignment_id"])
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
