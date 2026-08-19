"""Deterministic release gates for generated content."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .education import ASSESSMENT_COUNTS, COURSES
from .reports import report_specs
from .sec import verify_offline


def validate_reports(root: Path) -> dict[str, Any]:
    root = Path(root)
    issues: list[str] = []
    specs = report_specs()
    for code, expected in specs.items():
        path = root / f"{code}.json"
        if not path.is_file():
            issues.append(f"missing report spec {code}")
            continue
        actual = json.loads(path.read_text(encoding="utf-8"))
        titles = [s["title"] for s in actual.get("sections", [])]
        expected_titles = [s.title for s in expected.sections]
        if titles != expected_titles:
            issues.append(f"{code}: section order mismatch")
        if actual.get("report_type") != code:
            issues.append(f"{code}: wrong report_type")
    return {"ok": not issues, "specs": len(specs), "issues": issues}


def validate_education(root: Path) -> dict[str, Any]:
    root = Path(root)
    issues: list[str] = []
    assessments = sorted((root / "assessments").glob("*.json"))
    worlds = sorted((root / "submissions").glob("*.json"))
    gold = sorted((root / "gold").glob("*.json"))
    grading_worlds = sorted((root / "grading-worlds").glob("*.json"))
    expected_assessments = len(COURSES) * len(ASSESSMENT_COUNTS)
    if len(assessments) != expected_assessments:
        issues.append(f"expected {expected_assessments} assessments, found {len(assessments)}")
    question_count = 0
    submission_count = 0
    for path in assessments:
        payload = json.loads(path.read_text(encoding="utf-8"))
        question_count += len(payload.get("questions", []))
        if _contains_key(payload, "answer_key") or _contains_key(payload, "gold"):
            issues.append(f"public assessment leaks private answer data: {path.name}")
        for question in payload.get("questions", []):
            if not question.get("rubric"):
                issues.append(f"question missing rubric: {path.name}")
            elif sum(item.get("points", 0) for item in question["rubric"]) != question["question"].get("points"):
                issues.append(f"rubric total mismatch: {path.name}:{question['question'].get('question_id')}")
    for path in worlds:
        payload = json.loads(path.read_text(encoding="utf-8"))
        submission_count += len(payload.get("submissions", []))
        if _contains_key(payload, "answer_key"):
            issues.append(f"submission world contains answer_key: {path.name}")
    if len(gold) != expected_assessments:
        issues.append(f"expected {expected_assessments} private gold files, found {len(gold)}")
    if len(grading_worlds) != expected_assessments:
        issues.append(f"expected {expected_assessments} grading worlds, found {len(grading_worlds)}")
    task_manifest = root / "task-manifest.json"
    if task_manifest.is_file() and len(json.loads(task_manifest.read_text(encoding="utf-8")).get("task_ids", [])) != expected_assessments:
        issues.append("education task manifest count mismatch")
    for path in grading_worlds:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if _contains_key(payload, "answer_key"):
            issues.append(f"grading world contains answer_key: {path.name}")
    if question_count != 296:
        issues.append(f"expected 296 questions, found {question_count}")
    if submission_count != 320:
        issues.append(f"expected 320 submissions, found {submission_count}")
    return {"ok": not issues, "assessments": len(assessments),
            "questions": question_count, "submissions": submission_count,
            "gold": len(gold), "grading_worlds": len(grading_worlds), "issues": issues}


def _contains_key(value: Any, key: str) -> bool:
    """Detect a JSON key without false positives from paths or prose."""
    if isinstance(value, dict):
        return key in value or any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def validate_sec(root: Path) -> dict[str, Any]:
    result = verify_offline(Path(root))
    manifest_path = Path(root) / "release-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result["filings"] = manifest.get("filings", 0)
        result["normalized_facts"] = manifest.get("normalized_facts", 0)
    return result
