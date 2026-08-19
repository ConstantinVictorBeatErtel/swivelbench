from envs.commercial_banking.credit_reports import (
    REPORT_LAYOUTS, generate_scenarios, make_scenario, score_report,
)
from envs.commercial_banking.public_companies import catalog_companies, financial_snapshot


def test_credit_catalog_has_six_contrasting_companies_and_financials() -> None:
    companies = catalog_companies()
    assert {c.ticker for c in companies} == {"ADBE", "COST", "DAL", "CAT", "NEE", "HCA"}
    assert all(financial_snapshot(c.ticker)["revenue"] > 0 for c in companies)


def test_credit_scenario_score_requires_company_and_layout() -> None:
    scenario = make_scenario(51000)
    report = {"ticker": scenario.company.ticker,
              "sections": list(scenario.layout),
              "financials": {k: scenario.facts[k] for k in ("revenue", "ebitda", "total_debt", "interest_expense")},
              "ratios": {k: scenario.facts[k] for k in ("gross_leverage", "net_leverage", "interest_coverage", "ebitda_margin")},
              "recommendation": "approve_with_conditions"}
    assert score_report(report, scenario)["task_passed"] is True
    report["ticker"] = "WRONG"
    assert score_report(report, scenario)["task_passed"] is False


def test_credit_split_sizes_and_layouts() -> None:
    scenarios = generate_scenarios()
    assert len(scenarios) == 192
    assert len({s.company.ticker for s in scenarios if s.split == "test"}) >= 2
    assert set(REPORT_LAYOUTS).issuperset({s.report_type for s in scenarios})
