"""Small public types used by the teaching benchmark and browser UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RubricItem:
    item_id: str
    label: str
    max_points: int
    criterion: str


@dataclass(frozen=True)
class Question:
    question_id: str
    number: str
    kind: str
    prompt: str
    points: int
    rubric: tuple[RubricItem, ...]


@dataclass(frozen=True)
class SubmissionPage:
    page_id: str
    page_number: int
    image_path: str
    question_ids: tuple[str, ...]
    width: int
    height: int
    rotation: int = 0


@dataclass
class Submission:
    submission_id: str
    student_id: str
    student_name: str
    version: str
    pages: list[SubmissionPage]
    question_grades: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class GraderAssignment:
    grader_id: str
    display_name: str
    assignment_id: str
    question_ids: tuple[str, ...]
    source_message_id: str


def public_question(q: Question) -> dict[str, Any]:
    return {
        "question_id": q.question_id,
        "number": q.number,
        "kind": q.kind,
        "prompt": q.prompt,
        "points": q.points,
        "rubric": [
            {"item_id": i.item_id, "label": i.label, "max_points": i.max_points,
             "criterion": i.criterion}
            for i in q.rubric
        ],
    }


def public_submission(s: Submission) -> dict[str, Any]:
    return {
        "submission_id": s.submission_id,
        "student_id": s.student_id,
        "student_name": s.student_name,
        "version": s.version,
        "pages": [
            {"page_id": p.page_id, "page_number": p.page_number,
             "image_path": p.image_path, "question_ids": list(p.question_ids),
             "width": p.width, "height": p.height, "rotation": p.rotation}
            for p in s.pages
        ],
    }
