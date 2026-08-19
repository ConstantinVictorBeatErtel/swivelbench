"""Format-check unit coverage for OOXML deliverables."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from core.artifacts import write_docx, write_xlsx
from core.format_check import check_domain


def _grades_db(path: Path, rows: list[tuple[str, int]]) -> Path:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE grades (grade_id TEXT, submission_id TEXT, "
        "user_id TEXT, grade_total INTEGER, comment TEXT, graded_at TEXT)")
    con.executemany(
        "INSERT INTO grades VALUES (?,?,?,?,?,?)",
        [(f"GRD-{i}", sub, f"U-{i}", total, "", "now")
         for i, (sub, total) in enumerate(rows, start=1)])
    con.commit()
    con.close()
    return path


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
        db = _grades_db(art / "gradescope.db",
                        [("SUB-1", 10), ("SUB-2", 2), ("SUB-3", 0)])
        out = {c.id: c for c in check_domain("grading", art, path_b=db)}
        assert out["F1"].passed, out["F1"].detail
        assert out["F2"].passed, out["F2"].detail


def test_gr_format_fail_no_export():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        out = {c.id: c for c in check_domain("grading", art, path_b=None)}
        assert not out["F1"].passed
        assert not out["F2"].passed


def test_gr_format_fail_stale_export():
    """A docx exported before a later regrade must fail the staleness check
    even though it is a structurally valid gradesheet (P7)."""
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        (art / "reports").mkdir()
        write_docx(
            art / "reports" / "gradescope_gradesheet.docx",
            title="Gradescope Gradesheet",
            sections=[("SUB-1 · Ada", "Q1: 5\nQ2: 5\nTotal: 10")],
        )
        # Grade changed (e.g. a regrade adjustment) after the export was taken.
        db = _grades_db(art / "gradescope.db", [("SUB-1", 8)])
        out = {c.id: c for c in check_domain("grading", art, path_b=db)}
        assert not out["F1"].passed
        assert not out["F2"].passed
        assert "SUB-1" in out["F2"].detail
