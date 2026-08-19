"""Tool schemas for grading."""
from __future__ import annotations

from core.tool_schemas import I, S, _t
from envs.grading.policy import ACTION_CODES

SYSTEM_A = "inbox"
SYSTEM_B = "gradescope"


def make_tools() -> list[dict]:
    return [
        _t("list_emails",
           "List professor emails with instructions/rubrics (may be messy).",
           {}, []),
        _t("get_email",
           "Get one email body plus linked rubric_draft rows.",
           {"email_id": S}, ["email_id"]),
        _t("list_assignments", "List Gradescope assignments.", {}, []),
        _t("list_submissions",
           "Open the Gradescope submission queue for an assignment "
           "(without answer text).",
           {"assignment_id": S}, ["assignment_id"]),
        _t("get_submission",
           "Get one submission including visible_answer and clarity flags.",
           {"submission_id": S}, ["submission_id"]),
        _t("list_students", "List Gradescope students.", {}, []),
        _t("get_rubric", "Get the published rubric for an assignment.",
           {"assignment_id": S}, ["assignment_id"]),
        _t("list_regrade_requests", "List regrade requests.",
           {"status": {**S, "description": "optional filter: open|upheld|adjusted"}},
           []),
        _t("get_grade", "Get the grade and item scores for a submission.",
           {"submission_id": S}, ["submission_id"]),
        _t("publish_rubric",
           "Publish a reconciled rubric to Gradescope from a winning email.",
           {"assignment_id": S, "source_email_id": S,
            "items": {"type": "array", "items": {"type": "object"}}},
           ["assignment_id", "source_email_id", "items"]),
        _t("set_item_scores",
           "Set per-rubric-item scores for a submission (creates/updates grade). "
           "Does not export a gradesheet file — call export_gradesheet "
           "separately once grading is done.",
           {"submission_id": S, "user_id": S,
            "item_scores": {"type": "object", "additionalProperties": I},
            "comment": S},
           ["submission_id", "user_id", "item_scores"]),
        _t("export_gradesheet",
           "Render the current Gradescope grades for an assignment to a real "
           ".docx gradesheet. Call again after any later regrade changes a "
           "grade_total — the exported file is graded as live state, not a "
           "one-time snapshot.",
           {"assignment_id": S}, ["assignment_id"]),
        _t("resolve_regrade",
           "Uphold or adjust a regrade request. When decision='adjust', "
           "item_scores (the corrected per-item points) is required — "
           "grade_total is recomputed as their sum and grade_items is "
           "rewritten to match, so the two can never disagree. This does "
           "not write the audit log — call log_action separately to record "
           "the resolution.",
           {"regrade_id": S,
            "decision": {**S, "enum": ["uphold", "adjust"]},
            "resolution_note": S,
            "item_scores": {"type": ["object", "null"],
                            "additionalProperties": I}},
           ["regrade_id", "decision", "resolution_note"]),
        _t("log_action",
           f"Append an entry to the {SYSTEM_B} audit log.",
           {"actor": S,
            "action": {**S, "enum": list(ACTION_CODES)},
            "target_system": {**S, "enum": [SYSTEM_A, SYSTEM_B]},
            "target_key": S, "note": S},
           ["actor", "action", "target_system", "target_key", "note"]),
        _t("request_approval",
           "Escalate an ambiguous grading decision.",
           {"target": S, "proposed_change": S, "rationale": S},
           ["target", "proposed_change", "rationale"]),
        _t("finish", "Call when grading and regrades are complete.",
           {"summary": S}, ["summary"]),
    ]
