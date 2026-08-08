"""Deterministic OOXML format checks for Excel/Word deliverables.

These are not an LLM judge. They unzip the produced .xlsx / .docx and check
that the agent left a correctly structured Office file — the format contract
described in docs/format_judgement.md and in each domain POLICY.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FormatCheck:
    id: str
    kind: str  # always "format"
    weight: float
    critical: bool
    title: str
    why: str
    passed: bool
    detail: str = ""


def check_domain(domain: str, artifacts_dir: Path | None) -> list[FormatCheck]:
    art = Path(artifacts_dir) if artifacts_dir else None
    if domain == "commercial_banking":
        return _check_cb(art)
    if domain == "grading":
        return _check_gr(art)
    return []


def _check_cb(art: Path | None) -> list[FormatCheck]:
    xlsx = _newest(art / "excel" if art else None, "*.xlsx")
    docx = _newest(art / "reports" if art else None, "*_credit_memo.docx")
    x_ok, x_detail = _xlsx_financial_model(xlsx)
    d_ok, d_detail = _docx_sections(
        docx,
        title_must_contain=None,
        required_headings=[
            "Executive Summary",
            "Financial Analysis",
            "Covenant Review",
            "Recommendation",
        ],
    )
    return [
        FormatCheck(
            id="F1", kind="format", weight=1.0, critical=False,
            title="Excel model is a real formatted workbook",
            why=(
                "The .xlsx must open as OOXML with a Model sheet, a Field/Value "
                "header, and rows for revenue, ebitda, total_debt, "
                "interest_expense, and leverage."
            ),
            passed=x_ok, detail=x_detail,
        ),
        FormatCheck(
            id="F2", kind="format", weight=1.0, critical=False,
            title="Credit memo is a real formatted Word doc",
            why=(
                "The .docx must be OOXML with the four required section headings "
                "in order, each followed by a non-empty body."
            ),
            passed=d_ok, detail=d_detail,
        ),
    ]


def _check_gr(art: Path | None) -> list[FormatCheck]:
    docx = _newest(art / "reports" if art else None, "gradescope_gradesheet.docx")
    ok, detail = _docx_sections(
        docx,
        title_must_contain="Gradescope Gradesheet",
        required_headings=None,  # headings are submission ids; require Total lines
        require_total_lines=3,
    )
    return [
        FormatCheck(
            id="F1", kind="format", weight=1.0, critical=False,
            title="Gradesheet is a real formatted Word doc",
            why=(
                "The .docx must be OOXML titled Gradescope Gradesheet and list "
                "each graded submission with a Total line."
            ),
            passed=ok, detail=detail,
        ),
    ]


def _newest(folder: Path | None, pattern: str) -> Path | None:
    if folder is None or not folder.is_dir():
        return None
    hits = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def _read_zip_text(path: Path, inner: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            return z.read(inner).decode("utf-8", errors="replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def _xlsx_financial_model(path: Path | None) -> tuple[bool, str]:
    if path is None or not path.is_file():
        return False, "No .xlsx artifact was produced."
    sheet = _read_zip_text(path, "xl/worksheets/sheet1.xml")
    wb = _read_zip_text(path, "xl/workbook.xml")
    if sheet is None or wb is None:
        return False, f"{path.name} is not a valid OOXML workbook."
    if "name=\"Model\"" not in wb and "name='Model'" not in wb:
        return False, f"{path.name} is missing a sheet named Model."
    text = _strip_xml(sheet).lower()
    if "field" not in text or "value" not in text:
        return False, f"{path.name} is missing the Field/Value header row."
    missing = [k for k in (
        "revenue", "ebitda", "total_debt", "interest_expense", "leverage"
    ) if k not in text]
    if missing:
        return False, f"{path.name} missing field rows: {', '.join(missing)}."
    return True, f"{path.name} has Model sheet + required Field/Value rows."


def _docx_sections(
    path: Path | None,
    *,
    title_must_contain: str | None,
    required_headings: list[str] | None,
    require_total_lines: int = 0,
) -> tuple[bool, str]:
    if path is None or not path.is_file():
        return False, "No .docx artifact was produced."
    doc = _read_zip_text(path, "word/document.xml")
    if doc is None:
        return False, f"{path.name} is not a valid OOXML document."
    paras = re.findall(r"<w:t[^>]*>(.*?)</w:t>", doc, flags=re.DOTALL)
    # Unescape minimal entities used by our writer
    paras = [p.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'") for p in paras]
    if not paras:
        return False, f"{path.name} has no readable paragraphs."
    if title_must_contain and title_must_contain not in paras[0]:
        return False, (
            f"{path.name} title is {paras[0]!r}, expected to contain "
            f"{title_must_contain!r}."
        )
    if required_headings:
        # Find heading positions; each must be followed by a non-empty body
        # paragraph before the next heading.
        positions = []
        for h in required_headings:
            try:
                positions.append(paras.index(h))
            except ValueError:
                return False, f"{path.name} missing required heading {h!r}."
        if positions != sorted(positions):
            return False, f"{path.name} section headings are out of order."
        for i, h in enumerate(required_headings):
            start = positions[i] + 1
            end = positions[i + 1] if i + 1 < len(positions) else len(paras)
            body = [p.strip() for p in paras[start:end] if p.strip()]
            if not body:
                return False, f"{path.name} heading {h!r} has an empty body."
    if require_total_lines:
        totals = sum(1 for p in paras if p.strip().startswith("Total:"))
        if totals < require_total_lines:
            return False, (
                f"{path.name} has {totals} Total line(s); "
                f"need at least {require_total_lines}."
            )
    return True, f"{path.name} matches the required document format."


def _strip_xml(xml: str) -> str:
    return re.sub(r"<[^>]+>", " ", xml)
