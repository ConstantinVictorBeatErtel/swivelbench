"""Credit-report layouts and deterministic scenario randomization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.scenarios import rng_for
from .public_companies import PublicCompanyRequest, catalog_companies, financial_snapshot


REPORT_LAYOUTS: dict[str, tuple[str, ...]] = {
    "annual_review": ("Decision Header", "Borrower Overview", "Historical Financials",
                      "Leverage and Coverage", "Risks and Mitigants", "Recommendation"),
    "new_money_underwriting": ("Decision Header", "Request and Structure", "Business Analysis",
                               "Historical Financials", "Pro Forma Credit Metrics", "Conditions and Covenants",
                               "Recommendation"),
    "amendment_waiver": ("Decision Header", "Existing Facility", "Requested Amendment",
                          "Covenant Headroom", "Risk Analysis", "Approval Conditions"),
    "watchlist_early_warning": ("Decision Header", "Trigger Summary", "Trend Analysis",
                                "Liquidity and Debt", "Monitoring Plan", "Recommendation"),
}


@dataclass(frozen=True)
class CreditScenario:
    scenario_id: str
    split: str
    seed: int
    company: PublicCompanyRequest
    report_type: str
    request: dict[str, Any]
    layout: tuple[str, ...]
    facts: dict[str, float]


def ratios(financials: dict[str, Any]) -> dict[str, float]:
    ebitda = float(financials.get("ebitda", 0))
    debt = float(financials.get("total_debt", 0))
    interest = float(financials.get("interest_expense", 0))
    cash = float(financials.get("cash", 0))
    revenue = float(financials.get("revenue", 0))
    return {"gross_leverage": debt / ebitda if ebitda else 0.0,
            "net_leverage": (debt - cash) / ebitda if ebitda else 0.0,
            "interest_coverage": ebitda / interest if interest else 0.0,
            "ebitda_margin": ebitda / revenue if revenue else 0.0}


def make_scenario(seed: int, split: str = "train") -> CreditScenario:
    companies = catalog_companies()
    company = companies[seed % len(companies)]
    rng = rng_for("credit", seed)
    report_type = rng.choice(list(REPORT_LAYOUTS))
    facts = {**financial_snapshot(company.ticker), **ratios(financial_snapshot(company.ticker))}
    limit = rng.choice((25.0, 50.0, 100.0, 250.0))
    request = {"facility": "revolver" if company.request_type == "revolving" else "term loan",
               "purpose": rng.choice(("working capital", "refinancing", "capital program")),
               "amount": limit, "tenor_years": rng.choice((3, 5, 7)),
               "covenant": rng.choice(("net_leverage <= 4.5x", "interest_coverage >= 2.0x"))}
    return CreditScenario(f"CR-{seed:05d}", split, seed, company, report_type,
                          request, REPORT_LAYOUTS[report_type], facts)


def generate_scenarios() -> list[CreditScenario]:
    return ([make_scenario(51000 + i, "train") for i in range(128)] +
            [make_scenario(52000 + i, "validation") for i in range(32)] +
            [make_scenario(53000 + i, "test") for i in range(32)])


def score_report(report: dict[str, Any], scenario: CreditScenario) -> dict[str, Any]:
    """Deterministic report score with mandatory company and layout checks."""
    company_ok = str(report.get("ticker", "")).upper() == scenario.company.ticker
    sections = list(report.get("sections") or [])
    layout_ok = sections == list(scenario.layout)
    metric_hits = 0
    for key in ("revenue", "ebitda", "total_debt", "interest_expense"):
        try:
            if abs(float(report.get("financials", {}).get(key)) - scenario.facts[key]) <= 1e-6:
                metric_hits += 1
        except (TypeError, ValueError):
            pass
    ratio_hits = sum(abs(float(report.get("ratios", {}).get(k, 1e99)) - scenario.facts[k]) <= 1e-6
                     for k in ("gross_leverage", "net_leverage", "interest_coverage", "ebitda_margin"))
    inference_ok = str(report.get("recommendation", "")).lower() in {"approve", "decline", "approve_with_conditions", "watch"}
    formatting_ok = all(isinstance(report.get(k), (str, list, dict)) for k in ("ticker", "sections"))
    score = 15 * company_ok + 25 * (metric_hits / 4) + 15 * (ratio_hits / 4) + 25 * inference_ok + 10 * layout_ok + 10 * formatting_ok
    mandatory = company_ok and layout_ok and inference_ok
    return {"score_100": round(score, 3), "task_passed": mandatory and score == 100,
            "company_correct": company_ok, "metric_hits": metric_hits,
            "ratio_hits": ratio_hits, "inference_correct": inference_ok,
            "layout_correct": layout_ok, "formatting_correct": formatting_ok}
