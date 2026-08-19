"""Deterministic synthetic course, email, rubric, and visual submission generator."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from core.scenarios import ScenarioManifest, rng_for, stable_seed
from .api import TeachingAPI
from .mail import FixtureMailbox, Message
from .models import GraderAssignment, Question, RubricItem, Submission, SubmissionPage

COURSES = (
    ("STAT-204", "Applied Data Reasoning", "statistics"),
    ("OPT-231", "Models and Optimization", "optimization"),
    ("ALG-218", "Algorithms in Practice", "algorithms"),
)
ASSIGNMENT_TYPES = ("homework", "quiz", "midterm", "final", "coding_problem_set")
STUDENTS = (("ST-104", "Mira Patel"), ("ST-219", "Jonah Reed"), ("ST-331", "Lena Wu"))


def _font(size: int):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _question_bank(course_kind: str, assignment_id: str) -> list[Question]:
    if course_kind == "statistics":
        rows = [("1", "numeric", "Estimate the sampling error for the reported mean.", 4,
                 ("setup", "States the sampling-error relationship", 2), ("value", "Computes a consistent estimate", 2)),
                ("2", "conceptual", "Explain why a held-out split is needed before model selection.", 4,
                 ("reason", "Connects selection to unseen performance", 3), ("clarity", "Uses a relevant example", 1)),
                ("3", "graph", "Sketch the expected residual pattern for a misspecified trend.", 4,
                 ("shape", "Shows the systematic pattern", 3), ("label", "Labels axes or residual direction", 1)),
                ("4", "code", "Write a short validation procedure for the supplied estimator.", 4,
                 ("procedure", "Includes train/validation separation", 3), ("metric", "Computes a comparison metric", 1))]
    elif course_kind == "optimization":
        rows = [("1", "derivation", "Derive the stationarity condition for the constrained objective.", 5,
                 ("condition", "Writes the correct first-order condition", 3), ("constraint", "Includes the active constraint", 2)),
                ("2", "numeric", "Calculate the feasible solution after the specified update.", 4,
                 ("update", "Applies the update correctly", 3), ("feasible", "Checks feasibility", 1)),
                ("3", "conceptual", "Describe when a greedy step is not globally safe.", 3,
                 ("counterexample", "Identifies a needed counterexample", 2), ("condition", "States a sufficient condition", 1)),
                ("4", "graph", "Draw the level set and indicate the search direction.", 4,
                 ("geometry", "Correct level-set geometry", 3), ("direction", "Correct search direction", 1))]
    else:
        rows = [("1", "trace", "Trace the algorithm on the supplied four-node input.", 4,
                 ("state", "Maintains the right state after each step", 3), ("result", "Reports the final result", 1)),
                ("2", "proof", "Give an invariant that supports the loop termination.", 4,
                 ("invariant", "States a maintained invariant", 3), ("termination", "Connects it to termination", 1)),
                ("3", "code", "Implement the requested operation with its stated complexity.", 5,
                 ("behavior", "Produces the required behavior", 3), ("complexity", "Meets the complexity bound", 2)),
                ("4", "conceptual", "Compare the two data structures for this workload.", 3,
                 ("tradeoff", "Names the relevant trade-off", 2), ("choice", "Chooses one for the workload", 1))]
    out = []
    for row in rows:
        number, kind, prompt, points, *items = row
        qid = f"{assignment_id}-Q{number}"
        out.append(Question(qid, number, kind, prompt, points, tuple(
            RubricItem(f"{qid}-{key}", label, pts, label) for key, label, pts in items)))
    return out


def _make_page(path: Path, title: str, lines: list[str], seed: int,
               noisy: bool = False, rotation: int = 0) -> tuple[int, int]:
    rng = random.Random(seed)
    im = Image.new("RGB", (1400, 1900), "white")
    draw = ImageDraw.Draw(im)
    draw.text((100, 80), title, fill="#17324d", font=_font(42))
    y = 170
    for line in lines:
        draw.text((110, y), line, fill="#1f2933", font=_font(30))
        y += 55
    if noisy:
        for _ in range(180):
            x, yy = rng.randrange(30, 1370), rng.randrange(20, 1870)
            draw.ellipse((x, yy, x + 2, yy + 2), fill=(190, 190, 190))
        im = im.filter(ImageFilter.GaussianBlur(0.35))
    if rotation:
        im = im.rotate(rotation, expand=True, fillcolor="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", optimize=True)
    return im.size


def _make_pdf(path: Path, title: str, lines: list[str]) -> None:
    """Create a real attachment PDF whose visual content is independently renderable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(54, height - 60, title)
    c.setFont("Helvetica", 10)
    y = height - 90
    for line in lines:
        c.drawString(58, y, line[:110])
        y -= 18
        if y < 54:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 54
    c.save()


def _email_messages(course: dict[str, Any], assignment: dict[str, Any],
                    questions: list[Question], allocations: list[GraderAssignment],
                    attachment_path: str) -> list[Message]:
    split_lines = [f"{a.display_name}: {', '.join(a.question_ids)}" for a in allocations]
    body = (f"Hi team,\n\nPlease help with {assignment['title']}. Read the attached "
            "solution notes and use the rubric items for consistent partial credit.\n\n"
            "Question allocation:\n" + "\n".join(split_lines) +
            "\n\nIf a scan is unclear, leave a concise note and flag it rather than guessing.\n"
            "Thanks for helping us close the queue.")
    attachment = {"attachment_id": "ATT-SOL-1", "filename": "solution_notes.pdf",
                  "path": attachment_path, "mime_type": "application/pdf"}
    return [Message("MSG-OLDER", "THR-1", "course-staff@example.edu",
                     f"{assignment['title']} - draft allocation", "2026-02-03T09:00:00Z",
                     "Earlier draft; please wait for the corrected split."),
            Message("MSG-LATEST", "THR-1", "course-staff@example.edu",
                    f"{assignment['title']} grading details", "2026-02-04T09:00:00Z",
                    body, (attachment,))]


def build_session(seed: int, root: Path, *, scenario_id: str | None = None,
                  difficulty: str = "medium") -> tuple[ScenarioManifest, TeachingAPI]:
    rng = rng_for("teaching", seed)
    course_code, course_name, course_kind = COURSES[seed % len(COURSES)]
    assignment_type = ASSIGNMENT_TYPES[(seed // len(COURSES)) % len(ASSIGNMENT_TYPES)]
    assignment_id = f"ASN-{seed:05d}"
    title = f"{course_name} {assignment_type.replace('_', ' ').title()}"
    questions = _question_bank(course_kind, assignment_id)
    allocation_ids = (questions[0].question_id, questions[2].question_id)
    allocation = GraderAssignment("GRADER-1", "Assigned grader", assignment_id,
                                  allocation_ids, "MSG-LATEST")
    allocations = {allocation.grader_id: allocation}
    course = {"course_id": course_code, "name": course_name, "kind": course_kind}
    assignment = {"assignment_id": assignment_id, "title": title,
                  "assignment_type": assignment_type, "course_id": course_code}
    asset_root = root / "assets" / assignment_id
    solution_path = asset_root / "solution_notes.pdf"
    # The attachment is represented by a stable generated page; a PDF wrapper is
    # created by callers that need a true PDF, while the browser can render PNGs.
    solution_lines = [q.number + ". " + q.prompt for q in questions]
    _make_page(asset_root / "solution_notes.png", "Solution notes (fixture)",
               solution_lines, stable_seed(seed, "sol"))
    _make_pdf(solution_path, "Solution notes (fixture)", solution_lines)
    messages = _email_messages(course, assignment, questions, [allocation], str(solution_path))
    mailbox = FixtureMailbox(messages)
    submissions: dict[str, Submission] = {}
    gold: dict[str, Any] = {"assigned": {allocation.grader_id: list(allocation_ids)},
                            "grades": {}, "source_message_id": "MSG-LATEST"}
    for idx, (student_id, student_name) in enumerate(STUDENTS):
        sid = f"SUB-{seed:05d}-{idx + 1}"
        page_path = asset_root / "submissions" / sid / "page-1.png"
        noisy = idx == 2 or (difficulty == "hard" and idx == 1)
        size = _make_page(page_path, f"{title} - {student_name}", [
            "Questions: " + ", ".join(q.number for q in questions) +
            "; response visible on this page.",
            "Work shown; inspect the diagram and calculations.",
            "Student notes: partial work may contain a plausible misconception."],
            stable_seed(seed, sid), noisy=noisy, rotation=0 if idx != 1 else 1)
        page = SubmissionPage(f"PAGE-{sid}-1", 1, str(page_path),
                              tuple(q.question_id for q in questions), *size)
        submissions[sid] = Submission(sid, student_id, student_name, "A",
                                       [page])
        item_gold = {}
        for q in questions:
            # Deterministic answer labels: the third scan has an intentionally
            # missed first criterion, giving the grader a useful partial-credit case.
            scores = {i.item_id: i.max_points for i in q.rubric}
            if idx == 2:
                scores[q.rubric[0].item_id] = 0
            item_gold[q.question_id] = {"item_scores": scores,
                                        "total": sum(scores.values())}
        gold["grades"][sid] = item_gold
    public = {"course": course, "assignment": assignment,
              "questions": [{"question_id": q.question_id, "number": q.number,
                             "kind": q.kind, "prompt": q.prompt, "points": q.points,
                             "rubric": [{"item_id": i.item_id, "label": i.label,
                                         "max_points": i.max_points,
                                         "criterion": i.criterion} for i in q.rubric]}
                            for q in questions],
              "submissions": [{"submission_id": s.submission_id,
                               "student_id": s.student_id,
                               "student_name": s.student_name,
                               "version": s.version,
                               "pages": [{"page_id": p.page_id, "page_number": p.page_number,
                                          "image_path": p.image_path,
                                          "question_ids": list(p.question_ids),
                                          "width": p.width, "height": p.height,
                                          "rotation": p.rotation} for p in s.pages]}
                              for s in submissions.values()],
              "grader_id": allocation.grader_id,
              "task_prompt": ("Read the latest grading email and attached notes. "
                              "Grade every assigned question for every submission, "
                              "using the visible work and rubric; do not grade other "
                              "questions. Leave feedback for partial or unclear work.")}
    manifest = ScenarioManifest(scenario_id or f"TA-{seed:05d}", "teaching",
                                "generated", seed, difficulty, public, gold,
                                {"course_kind": course_kind,
                                 "assignment_type": assignment_type,
                                 "scan_noise": difficulty == "hard"})
    return manifest, TeachingAPI(assignment_id, course, assignment, {q.question_id: q for q in questions},
                                submissions, allocations, mailbox)


def generate(*, seed: int, out: Path, difficulty: str = "medium") -> ScenarioManifest:
    manifest, _ = build_session(seed, out, difficulty=difficulty)
    manifest.write(out / "manifests")
    return manifest


def load_session(seed: int, root: Path, *, difficulty: str = "medium") -> TeachingAPI:
    return build_session(seed, root, difficulty=difficulty)[1]
