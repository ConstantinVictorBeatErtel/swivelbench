"""Deterministic teaching scores, including scope and formatting checks."""
from __future__ import annotations

from typing import Any

from .api import TeachingAPI


def score_session(api: TeachingAPI, grader_id: str = "GRADER-1") -> dict[str, Any]:
    allocation = set(api.allocations[grader_id].question_ids)
    gold = _gold_from_expected(api, grader_id)
    assigned_cells = {(sid, qid) for sid in api.submissions for qid in allocation}
    actual_cells = {(sid, qid) for sid, s in api.submissions.items()
                    for qid in s.question_grades}
    coverage = assigned_cells & actual_cells
    out_of_scope = actual_cells - assigned_cells
    exact = 0
    total = len(assigned_cells)
    feedback_ok = 0
    for sid, qid in assigned_cells:
        actual = api.submissions[sid].question_grades.get(qid)
        expected = gold[sid][qid]
        if actual and actual.get("item_scores") == expected["item_scores"]:
            exact += 1
        if actual and isinstance(actual.get("comment"), str) and actual["comment"].strip():
            feedback_ok += 1
    grade_accuracy = exact / total if total else 0.0
    scope_score = 1.0 if coverage == assigned_cells and not out_of_scope else (
        len(coverage) / total if total else 0.0)
    workflow = 1.0 if any(a["action"] == "get_thread" for a in api.audit) else 0.0
    export_ok = any(a["action"] == "export_gradesheet" for a in api.audit)
    formatting = (feedback_ok / total if total else 0.0) * (1.0 if export_ok else 0.0)
    mandatory = (not out_of_scope and coverage == assigned_cells and
                 workflow == 1.0 and export_ok)
    score = 35 * grade_accuracy + 25 * scope_score + 15 * workflow + 10 * formatting + 15 * grade_accuracy
    return {"score_100": round(score, 3), "task_passed": bool(mandatory and grade_accuracy == 1.0),
            "grade_accuracy": grade_accuracy, "scope_score": scope_score,
            "workflow_score": workflow, "formatting_score": formatting,
            "gradesheet_exported": export_ok,
            "assigned_cells": sorted(assigned_cells), "graded_cells": sorted(actual_cells),
            "out_of_scope": sorted(out_of_scope), "criteria_total": total,
            "criteria_passed": exact, "mandatory_failure": not mandatory}


def _gold_from_expected(api: TeachingAPI, grader_id: str) -> dict[str, dict[str, Any]]:
    # The generator keeps the semantic gold in a private attribute only in the
    # benchmark runner.  A compact deterministic fallback makes manually built
    # sessions useful in tests without exposing page text to the model.
    result = {}
    for sid, sub in api.submissions.items():
        result[sid] = {}
        for qid in api.allocations[grader_id].question_ids:
            q = api.questions[qid]
            scores = {i.item_id: i.max_points for i in q.rubric}
            if sid.endswith("-3"):
                scores[q.rubric[0].item_id] = 0
            result[sid][qid] = {"item_scores": scores, "total": sum(scores.values())}
    return result
