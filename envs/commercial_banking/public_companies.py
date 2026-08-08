"""Scaffold for public-company credit requests with real-number verification.

Company tickers and report-type roster are decided separately. This module
loads the catalog, exposes enabled companies, and builds SQL assertion
snippets that compare model cells to ground_truth_metrics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "fixtures" / "public_companies.json"


@dataclass(frozen=True)
class PublicCompanyRequest:
    company_id: str
    ticker: str
    legal_name: str
    request_type: str
    report_type: str
    ground_truth_metrics: dict
    enabled: bool = False


def load_catalog(path: Path = CATALOG_PATH) -> list[PublicCompanyRequest]:
    data = json.loads(path.read_text())
    out = []
    for row in data.get("companies", []):
        out.append(PublicCompanyRequest(
            company_id=row["company_id"],
            ticker=row["ticker"],
            legal_name=row["legal_name"],
            request_type=row["request_type"],
            report_type=row["report_type"],
            ground_truth_metrics=dict(row.get("ground_truth_metrics") or {}),
            enabled=bool(row.get("enabled")),
        ))
    return out


def enabled_companies(path: Path = CATALOG_PATH) -> list[PublicCompanyRequest]:
    return [c for c in load_catalog(path) if c.enabled]


def metrics_assertion_sql(request_id: str, metrics: dict, *,
                          assert_id: str = "PUB1") -> str:
    """Emit a rubric criterion that model cells match public ground truth.

    Skips null metrics. Leverage compared at 1e-9; others at 1e-6.
    """
    checks = []
    for key in ("revenue", "ebitda", "total_debt", "interest_expense", "leverage"):
        val = metrics.get(key)
        if val is None:
            continue
        tol = "1e-9" if key == "leverage" else "1e-6"
        checks.append(
            f"(mc.cell_key = '{key}' AND ABS(mc.cell_value - {float(val)}) < {tol})"
        )
    if not checks:
        return (
            f"-- @assert id={assert_id} kind=positive weight=1.0 "
            f"step=S3_model level=ground role=required\n"
            f"-- ground_truth_metrics not yet filled for {request_id}\n"
            f"SELECT 0;\n"
        )
    joined = "\n      OR ".join(checks)
    n = len(checks)
    return f"""-- @assert id={assert_id} kind=positive weight=1.0 step=S3_model level=ground role=required
SELECT (
  SELECT COUNT(*) FROM a.model_cells mc
  JOIN a.request_state rs ON rs.model_id = mc.model_id
  WHERE rs.request_id = '{request_id}'
    AND (
      {joined}
    )
) = {n};
"""


def report_type_note() -> str:
    data = json.loads(CATALOG_PATH.read_text())
    types = data.get("report_types_tbd") or []
    return (
        "Public-company credit book will require distinct report types "
        f"({', '.join(types)}). Catalog entries stay disabled until tickers "
        "and ground_truth_metrics are filled."
    )
