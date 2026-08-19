"""Assemble one machine-readable V1 release manifest from all content gates."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .banking import validate_banking
from .validators import validate_education, validate_reports, validate_sec


def build_release_manifest(root: Path = Path("data")) -> dict[str, Any]:
    root = Path(root)
    checks = {
        "reports": validate_reports(root / "banking/reports/specs"),
        "banking": validate_banking(root / "banking/content"),
        "education": validate_education(root / "education"),
        "sec": validate_sec(root / "banking/sec"),
    }
    manifest = {
        "schema": "swivelbench.content-release.v1",
        "content_version": "v1",
        "freeze_date": "2026-08-18",
        "generated_at": date.today().isoformat(),
        "checks": checks,
        "counts": {
            "companies": checks["sec"].get("companies", 0),
            "filings": checks["sec"].get("filings", 0),
            "normalized_facts": checks["sec"].get("normalized_facts", 0),
            "banking_scenarios": checks["banking"].get("scenarios", 0),
            "banking_references": checks["banking"].get("references", 0),
            "courses": 8,
            "assessments": checks["education"].get("assessments", 0),
            "questions": checks["education"].get("questions", 0),
            "submissions": checks["education"].get("submissions", 0),
            "grading_worlds": checks["education"].get("grading_worlds", 0),
        },
        "ready": all(check.get("ok", False) for check in checks.values()),
        "content_foundation_ready": all(check.get("ok", False) for check in checks.values()),
        "benchmark_ready": False,
        "known_blockers": [
            "independent solver, visual-grounding, originality, and release-owner review are not yet recorded",
            "15 existing grading trap-matrix fault cases fail repository-wide pytest",
        ],
    }
    output = root / "release-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
