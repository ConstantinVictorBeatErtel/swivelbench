"""Tests for calibration loop and public-company scaffold."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from envs.commercial_banking.public_companies import (  # noqa: E402
    enabled_companies,
    load_catalog,
    metrics_assertion_sql,
    report_type_note,
)
from eval.calibrate_criterion import (  # noqa: E402
    CalibrationCase,
    calibrate,
    heuristic_structure_judge,
)


def test_public_catalog_loads_disabled():
    cats = load_catalog()
    assert len(cats) >= 2
    assert enabled_companies() == []
    assert "report types" in report_type_note().lower() or "report" in report_type_note().lower()


def test_metrics_assertion_sql_skips_nulls():
    sql = metrics_assertion_sql("CRQ-1001", {"revenue": None, "leverage": 3.76})
    assert "leverage" in sql
    assert "3.76" in sql


def test_calibration_demo_passes():
    case = CalibrationCase(
        criterion_id="t",
        criterion_text='Must include "Executive Summary" and "Recommendation".',
        reference_artifact="Executive Summary\nHi\nRecommendation\nGo\n",
        hand_label_pass=True,
        adversarial_artifact="Executive Summary\nHi\n",
        adversarial_label_pass=False,
    )
    out = calibrate(case, heuristic_structure_judge)
    assert out.calibrated
