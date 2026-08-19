"""Grading (TA) policy text and helpers."""
from __future__ import annotations

ACTION_CODES = (
    "publish_rubric",
    "open_submissions",
    "grade_item",
    "resolve_regrade",
    "note",
)

POLICY_TEXT = """\
POLICY (follow exactly)

Rubric reconciliation (inbox → Gradescope)
  - Professor emails may conflict. Prefer the email with the latest sent_at.
  - Ignore HTML noise and outdated attachment references in the body; use the
    structured rubric_drafts rows linked to the winning email.
  - Publish exactly those rubric items. The sum of max_points must equal the
    winning email's stated_total_points.
  - Do not publish a rubric whose total disagrees with stated_total_points.

Grading submissions
  - Grade every submission against the published rubric items.
  - Score each rubric item as 0 when its expected_key does not appear in
    visible_answer (case-insensitive substring match). Otherwise award
    max_points — halved and floored to an integer when clarity = 'low' or
    handwriting_noise = 1, full max_points otherwise. This rule fully
    determines every score; do not invent content that is not in
    visible_answer, and do not award partial credit outside it.
  - Never grade a submission onto the wrong user_id. Identity: prefer exact
    gradescope user_id from the submission row; do not reassign by similar names.

Regrade requests
  - If the student claims points for an answer outside the rubric
    (claim_type = 'out_of_rubric'), uphold the original grade.
  - If claim_type = 'arithmetic' and the stored item scores do not sum to
    grade_total, adjust grade_total to the sum of item scores.
  - If claim_type = 'clarity_partial' and the submission had clarity=low,
    ensure each item score is at most floor(max_points / 2); adjust down if
    an agent over-scored.
  - Log every regrade resolution and every meaningful grading write. No tool
    writes the audit log for you; log_action is a separate, required call.

Audit discipline (call log_action with these action codes; no tool call
above writes the audit log as a side effect)
  - publish_rubric — after publishing a rubric to Gradescope
  - open_submissions — after opening the submission queue for an assignment
  - grade_item — after each set_item_scores call
  - resolve_regrade — after each resolve_regrade call
  - note — any other meaningful grading note worth recording

Deliverables (file formatting — graded)
  - Once every submission is graded, call export_gradesheet to write a real
    .docx gradesheet at artifacts/reports/gradescope_gradesheet.docx titled
    "Gradescope Gradesheet". set_item_scores does not write this file.
  - Each graded submission must appear as a heading with item lines and a
    Total: line.
  - If any later regrade changes a grade_total, call export_gradesheet again
    — the file is graded against the final state, not a one-time snapshot.
"""
