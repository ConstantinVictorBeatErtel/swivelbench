"""Format-check unit coverage for OOXML deliverables."""
from __future__ import annotations

import tempfile
from pathlib import Path

from core.artifacts import write_docx, write_xlsx
from core.format_check import check_domain


def test_cb_format_pass():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        (art / "excel").mkdir()
        (art / "reports").mkdir()
        write_xlsx(
            art / "excel" / "MDL.xlsx",
            title="MDL",
            rows=[
                ("revenue", 1), ("ebitda", 1), ("total_debt", 1),
                ("interest_expense", 1), ("leverage", 1.0),
            ],
        )
        write_docx(
            art / "reports" / "CRQ_credit_memo.docx",
            title="Memo",
            sections=[
                ("Executive Summary", "Body one."),
                ("Financial Analysis", "Body two."),
                ("Covenant Review", "Body three."),
                ("Recommendation", "Body four."),
            ],
        )
        out = {c.id: c for c in check_domain("commercial_banking", art)}
        assert out["F1"].passed and out["F2"].passed


def test_cb_format_fail_missing_section():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        (art / "excel").mkdir()
        (art / "reports").mkdir()
        write_xlsx(
            art / "excel" / "MDL.xlsx",
            title="MDL",
            rows=[
                ("revenue", 1), ("ebitda", 1), ("total_debt", 1),
                ("interest_expense", 1), ("leverage", 1.0),
            ],
        )
        write_docx(
            art / "reports" / "CRQ_credit_memo.docx",
            title="Memo",
            sections=[
                ("Executive Summary", "Body one."),
                ("Financial Analysis", "Body two."),
                ("Covenant Review", "Body three."),
            ],
        )
        out = {c.id: c for c in check_domain("commercial_banking", art)}
        assert out["F1"].passed
        assert not out["F2"].passed
        assert "Recommendation" in out["F2"].detail


def test_gr_format_pass():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        (art / "reports").mkdir()
        write_docx(
            art / "reports" / "gradescope_gradesheet.docx",
            title="Gradescope Gradesheet",
            sections=[
                ("SUB-1 · Ada", "Q1: 5\nQ2: 5\nTotal: 10"),
                ("SUB-2 · Bea", "Q1: 2\nQ2: 0\nTotal: 2"),
                ("SUB-3 · Cai", "Q1: 0\nQ2: 0\nTotal: 0"),
            ],
        )
        out = {c.id: c for c in check_domain("grading", art)}
        assert out["F1"].passed
