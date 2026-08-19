"""Create auditable research briefs and source ledgers for content production."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .education import COURSES
from .schemas import SourceRecord
from .sec import COMPANIES

SEC_API = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
SEC_DEV = "https://www.sec.gov/about/developer-resources"
OPENSTAX = "https://help.openstax.org/s/article/Licensing-information-of-OpenStax-textbooks"
MIT_OCW = "https://ocw.mit.edu/pages/privacy-and-terms-of-use/"


def write_research_artifacts(root: Path, *, sec_root: Path = Path("data/banking/sec")) -> dict[str, int]:
    root = Path(root)
    briefs = root / "briefs"
    company_briefs = briefs / "companies"
    course_briefs = briefs / "courses"
    for directory in (root, company_briefs, course_briefs):
        directory.mkdir(parents=True, exist_ok=True)
    accessed = date.today().isoformat()
    records: list[SourceRecord] = [
        SourceRecord("SEC-API", SEC_API, "U.S. Securities and Exchange Commission",
                     "EDGAR Application Programming Interfaces", accessed,
                     "U.S. government public data", "distributable",
                     notes="Submissions and Company Facts acquisition contract."),
        SourceRecord("SEC-DEV", SEC_DEV, "U.S. Securities and Exchange Commission",
                     "Developer Resources", accessed, "U.S. government public data",
                     "distributable", notes="Fair-access and identifying User-Agent guidance."),
        SourceRecord("OER-OPENSTAX-LICENSE", OPENSTAX, "OpenStax", "Licensing information",
                     accessed, "CC BY-NC-SA 4.0", "research_only",
                     notes="License reviewed; no questions or close paraphrases are distributed."),
        SourceRecord("OER-MITOCW-TERMS", MIT_OCW, "MIT OpenCourseWare", "Terms of Use",
                     accessed, "CC BY-NC-SA 4.0", "research_only",
                     notes="License reviewed; structural patterns only."),
    ]
    company_count = 0
    for ticker, meta in COMPANIES.items():
        manifest_path = Path(sec_root) / ticker / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        source_ids = []
        for filing in manifest.get("filings", []):
            sid = f"SEC-{ticker}-{filing['accession'].replace('-', '')}"
            source_ids.append(sid)
            records.append(SourceRecord(
                sid, filing["source_url"], "U.S. Securities and Exchange Commission",
                f"{ticker} {filing['form']} filed {filing['filed_date']}", accessed,
                "U.S. government public data", "distributable",
                sha256=filing["primary_sha256"], local_artifact=filing["local_artifact"],
                notes=f"Period end {filing['period_end']}; accession {filing['accession']}."))
        (company_briefs / f"{ticker}.md").write_text(
            f"# SEC research brief: {ticker}\n\n"
            f"- Company ID: `{meta['company_id']}`\n- CIK: `{meta['cik']}`\n"
            f"- Split: `{meta['split']}`\n- Filing freeze: `2026-08-18`\n"
            f"- Selected filing source IDs: {', '.join(source_ids) or 'pending acquisition'}\n\n"
            "## Research-only notes\n\n"
            "Facts must be cited to a selected filing accession, period, concept, unit, and local artifact. "
            "Business-risk prose is a research lead only; generators may not invent unsupported claims.\n",
            encoding="utf-8")
        company_count += 1
    for course in COURSES:
        (course_briefs / f"{course.course_id}.md").write_text(
            f"# Academic research brief: {course.title}\n\n"
            f"- Course split: `{course.split}`\n- Discipline: `{course.discipline}`\n"
            f"- Learning objectives: {', '.join(course.objectives)}\n"
            f"- Structural references: `OER-OPENSTAX-LICENSE`, `OER-MITOCW-TERMS`\n\n"
            "This brief records assessment-pattern research only. It contains no copied questions, answer keys, "
            "or adapted wording. Final content must be original and carry SwivelBench provenance.\n",
            encoding="utf-8")
    ledger = root / "source-ledger.jsonl"
    ledger.write_text("".join(json.dumps(record.to_dict(), sort_keys=True) + "\n" for record in records), encoding="utf-8")
    summary = {"sources": len(records), "company_briefs": company_count, "course_briefs": len(COURSES)}
    (root / "research-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
