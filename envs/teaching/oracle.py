"""Perfect scripted teaching grader used to validate generated fixtures."""
from __future__ import annotations

from pathlib import Path

from .generator import load_session
from .scoring import score_session


def run(api) -> None:
    grader = "GRADER-1"
    api.get_thread("THR-1")
    api.list_assigned_questions(grader)
    for sid in api.submissions:
        for qid in api.allocations[grader].question_ids:
            q = api.questions[qid]
            scores = {i.item_id: i.max_points for i in q.rubric}
            if sid.endswith("-3"):
                scores[q.rubric[0].item_id] = 0
            api.set_question_grade(sid, qid, scores, "Reviewed the visible work.", grader)
    api.export_gradesheet(Path("/tmp") / "swivelbench_teaching_gradesheet.docx")
    api.finish_assignment("Assigned questions graded.")


def verify_oracle(seed: int = 7101, root: Path | None = None) -> dict:
    root = root or Path("/tmp/swivelbench-teaching")
    api = load_session(seed, root)
    run(api)
    return score_session(api)
