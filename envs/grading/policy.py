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
  - For clarity = 'low' or handwriting_noise = 1: award at most half of
    max_points on each item (floor to integer). Do not invent content that is
    not in visible_answer.
  - For clarity = 'high' and handwriting_noise = 0: award full max_points if
    visible_answer is non-empty and matches the rubric item's expected_key
    (case-insensitive substring), else 0.
  - Never grade a submission onto the wrong user_id. Identity: prefer exact
    gradescope user_id from the submission row; do not reassign by similar names.

Regrade requests
  - If the student claims points for an answer outside the rubric
    (claim_type = 'out_of_rubric'), uphold the original grade.
  - If claim_type = 'arithmetic' and the stored item scores do not sum to
    grade_total, adjust grade_total to the sum of item scores.
  - If claim_type = 'clarity_partial' and the submission had clarity=low,
    ensure scores are at most half max; adjust down if an agent over-scored.
  - Log every regrade resolution.
"""
