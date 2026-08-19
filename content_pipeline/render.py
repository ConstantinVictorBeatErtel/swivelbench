"""Deterministic text-first renderers for content artifacts."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .reports import report_specs


def render_submission_text(submission: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"Submission {submission['submission_id']}",
             f"Profile: {submission['profile_id']}", ""]
    for response in submission["responses"]:
        lines.extend([
            f"Question {response['question_id']}",
            response["visible_response"],
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_submission_pdf(submission: dict[str, Any], path: Path) -> Path:
    """Render a readable PDF when reportlab is installed.

    The text artifact remains the canonical representation; PDF generation is
    an output step and never changes the response or its score.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("install the content extra to render PDFs") from exc
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 48
    c.setFont("Helvetica-Bold", 14)
    c.drawString(48, y, f"Submission {submission['submission_id']}")
    y -= 24
    c.setFont("Helvetica", 10)
    for response in submission["responses"]:
        raw_lines = (f"Question {response['question_id']}",
                     *response["visible_response"].splitlines(), "")
        for raw_line in raw_lines:
            for line in _wrap_text(raw_line, 115):
                if y < 54:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 48
                c.drawString(48, y, line)
                y -= 16
    c.save()
    return path


def render_submission_png(submission: dict[str, Any], path: Path) -> Path:
    """Render a deterministic scan-like image for visual grading tests."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("install the content extra to render PNGs") from exc
    image = Image.new("RGB", (1400, 1900), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    rng = random.Random(submission.get("seed", 0))
    y = 50
    if submission.get("format") == "handwritten_scan":
        for guide_y in range(92, 1880, 52):
            draw.line((35, guide_y, 1360, guide_y), fill=(226, 232, 238), width=1)
    lines = [f"Submission {submission['submission_id']}"]
    for response in submission["responses"]:
        lines.extend([response["question_id"], *response["visible_response"].splitlines(), ""])
    for raw_line in lines:
        for line in _wrap_text(raw_line, 88):
            jitter = rng.choice([-2, -1, 0, 0, 1, 2]) if submission.get("format") == "handwritten_scan" else 0
            ink = (70, 78, 88) if submission.get("format") == "handwritten_scan" else (20, 30, 40)
            draw.text((55 + jitter, y), line, fill=ink, font=font)
            y += 42
    image.save(path, format="PNG", optimize=True)
    return path


def render_education_world(world_path: Path, out_root: Path) -> dict[str, int]:
    world = json.loads(Path(world_path).read_text(encoding="utf-8"))
    out_root = Path(out_root)
    count = 0
    for submission in world["submissions"]:
        base = out_root / submission["submission_id"]
        render_submission_text(submission, base.with_suffix(".md"))
        render_submission_pdf(submission, base.with_suffix(".pdf"))
        render_submission_png(submission, base.with_suffix(".png"))
        count += 1
    return {"submissions": count}


def render_assessment_pdf(assessment_path: Path, out_root: Path) -> Path:
    """Render an exam/homework sheet with prompts, points, and work space."""
    assessment = json.loads(Path(assessment_path).read_text(encoding="utf-8"))
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    aid = assessment["assessment"]["assessment_id"]
    path = out_root / f"{aid}.pdf"
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the content extra to render PDFs") from exc
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 48
    c.setFont("Helvetica-Bold", 16)
    c.drawString(48, y, assessment["assessment"]["title"])
    y -= 22
    c.setFont("Helvetica", 9)
    c.drawString(48, y, "Show equations, substitutions, intermediate reasoning, and a final labeled answer.")
    y -= 26
    c.setFont("Helvetica", 10)
    for index, item in enumerate(assessment["questions"], 1):
        question = item["question"]
        prompt_lines = _wrap_text(f"{index}. [{question['points']} pts] {question['prompt']}", 105)
        for line in prompt_lines:
            if y < 68:
                c.showPage(); c.setFont("Helvetica", 10); y = height - 48
            c.drawString(48, y, line)
            y -= 14
        c.setStrokeColorRGB(0.78, 0.80, 0.83)
        for _ in range(4 if question["points"] >= 7 else 3):
            if y < 58:
                c.showPage(); c.setFont("Helvetica", 10); y = height - 48
            c.line(60, y, width - 52, y)
            y -= 18
        y -= 12
    c.save()
    return path


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def render_report_templates(out_root: Path) -> dict[str, int]:
    """Create deterministic DOCX templates from the typed report contracts."""
    from core.artifacts import write_docx

    out_root = Path(out_root)
    count = 0
    for code, spec in report_specs().items():
        sections = []
        for section in spec.sections:
            body = "\n".join([
                "Expected content: " + section.purpose,
                "Required evidence: " + ", ".join(section.required_evidence),
                "Required calculations: " + ", ".join(section.calculations),
                "Required claims: " + ", ".join(section.required_claims),
                "Forbidden claims: " + ", ".join(section.forbidden_claims),
                "Verifier IDs: " + ", ".join(section.verifier_ids),
                "Placeholder: complete from the approved source brief and scenario overlay.",
            ])
            sections.append((section.title, body))
        write_docx(out_root / f"{code}.docx", title=spec.title, sections=sections)
        count += 1
    return {"templates": count}
