"""Stateful question-level grading API.

Writes intentionally remain possible outside the current allocation so the
scorer can detect scope violations instead of hiding them behind permissions.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .mail import FixtureMailbox
from .models import GraderAssignment, Question, Submission, public_question, public_submission
from core.artifacts import write_docx


@dataclass
class TeachingAPI:
    assignment_id: str
    course: dict[str, Any]
    assignment: dict[str, Any]
    questions: dict[str, Question]
    submissions: dict[str, Submission]
    allocations: dict[str, GraderAssignment]
    mailbox: FixtureMailbox

    def __post_init__(self) -> None:
        self.audit: list[dict[str, Any]] = []
        self._initial_grades = copy.deepcopy({
            sid: s.question_grades for sid, s in self.submissions.items()})

    def close(self) -> None:
        """Compatibility no-op for the two-database domain runner."""
        return None

    def _log(self, action: str, target: str, **extra: Any) -> None:
        self.audit.append({"action": action, "target": target, **extra})

    def search_messages(self, query: str = "") -> dict[str, Any]:
        self._log("search_messages", query)
        return self.mailbox.search_messages(query)

    def get_message(self, message_id: str) -> dict[str, Any]:
        self._log("get_message", message_id)
        return self.mailbox.get_message(message_id)

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        self._log("get_thread", thread_id)
        return self.mailbox.get_thread(thread_id)

    def list_assignments(self) -> dict[str, Any]:
        self._log("list_assignments", self.assignment_id)
        return {"assignments": [{**self.assignment, "course": self.course}]}

    def list_assigned_questions(self, grader_id: str) -> dict[str, Any]:
        a = self.allocations.get(grader_id)
        self._log("list_assigned_questions", grader_id)
        if not a:
            return {"ok": False, "error": "unknown_grader"}
        return {"ok": True, "assignment": {"grader_id": a.grader_id,
            "display_name": a.display_name, "question_ids": list(a.question_ids),
            "source_message_id": a.source_message_id},
            "questions": [public_question(self.questions[q]) for q in a.question_ids]}

    def list_submissions(self) -> dict[str, Any]:
        self._log("list_submissions", self.assignment_id)
        return {"submissions": [public_submission(s) for s in self.submissions.values()]}

    def get_submission_pages(self, submission_id: str) -> dict[str, Any]:
        s = self.submissions.get(submission_id)
        self._log("get_submission_pages", submission_id)
        if not s:
            return {"ok": False, "error": "not_found"}
        # No answer text, OCR, gold labels, or hidden source annotations.
        return {"ok": True, "submission_id": submission_id,
                "student_id": s.student_id, "student_name": s.student_name,
                "version": s.version, "pages": [p.__dict__ for p in s.pages]}

    def get_question(self, question_id: str) -> dict[str, Any]:
        self._log("get_question", question_id)
        q = self.questions.get(question_id)
        return {"ok": bool(q), "question": public_question(q) if q else None}

    def get_rubric(self, question_id: str) -> dict[str, Any]:
        self._log("get_rubric", question_id)
        q = self.questions.get(question_id)
        return {"ok": bool(q), "items": [
            {"item_id": i.item_id, "label": i.label, "max_points": i.max_points,
             "criterion": i.criterion} for i in (q.rubric if q else ())]}

    def set_question_grade(self, submission_id: str, question_id: str,
                           item_scores: dict[str, int], comment: str = "",
                           grader_id: str = "") -> dict[str, Any]:
        s = self.submissions.get(submission_id)
        q = self.questions.get(question_id)
        args = {"submission_id": submission_id, "question_id": question_id,
                "item_scores": item_scores, "comment": comment,
                "grader_id": grader_id}
        self._log("set_question_grade", f"{submission_id}:{question_id}", **args)
        if not s or not q:
            return {"ok": False, "error": "not_found"}
        allowed = set(self.allocations.get(grader_id, GraderAssignment(
            "", "", self.assignment_id, (), "")).question_ids)
        in_scope = question_id in allowed
        valid = {i.item_id: i.max_points for i in q.rubric}
        errors = []
        for key, value in item_scores.items():
            if key not in valid:
                errors.append(f"unknown rubric item {key}")
            elif not isinstance(value, int) or value < 0 or value > valid[key]:
                errors.append(f"invalid points for {key}")
        if errors:
            return {"ok": False, "error": "invalid_value", "details": errors,
                    "in_scope": in_scope}
        s.question_grades[question_id] = {
            "grader_id": grader_id, "item_scores": dict(item_scores),
            "total": sum(item_scores.values()), "comment": comment,
            "in_scope": in_scope}
        return {"ok": True, "in_scope": in_scope,
                "total": s.question_grades[question_id]["total"]}

    def get_grades(self) -> dict[str, Any]:
        self._log("get_grades", self.assignment_id)
        return {"grades": {sid: copy.deepcopy(s.question_grades)
                            for sid, s in self.submissions.items()}}

    def finish_assignment(self, summary: str = "") -> dict[str, Any]:
        self._log("finish_assignment", self.assignment_id, summary=summary)
        return {"ok": True, "summary": summary}

    def export_gradesheet(self, path) -> dict[str, Any]:
        """Write a real OOXML gradesheet containing question-level totals."""
        sections = []
        for sid, sub in self.submissions.items():
            lines = []
            total = 0
            for qid, grade in sorted(sub.question_grades.items()):
                lines.append(f"{qid}: {grade['total']}")
                total += int(grade["total"])
                if grade.get("comment"):
                    lines.append(f"Comment: {grade['comment']}")
            lines.append(f"Total: {total}")
            sections.append((f"{sid} · {sub.student_name}", "\n".join(lines)))
        write_docx(path, title="Gradescope Gradesheet", sections=sections)
        self._log("export_gradesheet", str(path))
        return {"ok": True, "path": str(path), "submission_count": len(sections)}
