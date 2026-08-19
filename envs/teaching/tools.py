"""Tool schemas for the typed teaching track."""
from __future__ import annotations

from core.tool_schemas import I, S, _t


def make_tools() -> list[dict]:
    return [
        _t("search_messages", "Search the seeded Gmail-compatible mailbox.", {"query": S}, []),
        _t("get_message", "Read one assignment message and attachment metadata.", {"message_id": S}, ["message_id"]),
        _t("get_thread", "Read all messages in a thread in chronological order.", {"thread_id": S}, ["thread_id"]),
        _t("list_assignments", "List the current course assignments.", {}, []),
        _t("list_assigned_questions", "List exactly the questions allocated to this grader.", {"grader_id": S}, ["grader_id"]),
        _t("list_submissions", "List submission identities and page metadata without answers.", {}, []),
        _t("get_submission_pages", "Open rendered submission pages; returns pixels only.", {"submission_id": S}, ["submission_id"]),
        _t("get_question", "Read one question and its public prompt.", {"question_id": S}, ["question_id"]),
        _t("get_rubric", "Read rubric items for one question.", {"question_id": S}, ["question_id"]),
        _t("set_question_grade", "Write one question's rubric scores and feedback.", {
            "submission_id": S, "question_id": S, "grader_id": S,
            "item_scores": {"type": "object", "additionalProperties": I},
            "comment": S}, ["submission_id", "question_id", "grader_id", "item_scores"]),
        _t("get_grades", "Read current question-level grades.", {}, []),
        _t("export_gradesheet", "Export a real Word gradesheet after grading.", {"path": S}, ["path"]),
        _t("finish_assignment", "Finish after all assigned questions are graded.", {"summary": S}, ["summary"]),
    ]
