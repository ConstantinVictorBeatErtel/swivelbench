"""Commercial-credit report specifications and deterministic emitters."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import ReportSectionSpec, ReportSpec


SECTION_EXPECTATIONS = {
    "Decision Header": "Identify the borrower, report date, request type, decision sought, exposure, risk rating, and preparer; keep the decision visible without unsupported conclusions.",
    "Relationship and Exposure Summary": "Summarize relationship tenure, products, committed and outstanding exposure, guarantors, and concentration context using the scenario overlay.",
    "Borrower and Business Overview": "Describe the borrower’s legal/business profile, products, customers, revenue model, ownership, and management facts supported by the filing or scenario.",
    "Industry and Competitive Position": "Explain sector conditions, competitive position, cyclicality, and operating risks; label external interpretation separately from filing evidence.",
    "Historical Financial Performance": "Present comparable filing periods for revenue, operating income, net income, margins, and material trends with period and unit labels.",
    "Leverage, Coverage, and Cash Flow": "Show debt, net debt, coverage, operating cash flow, capex, and formula-based ratios; identify unavailable components instead of proxying them.",
    "Liquidity and Debt Maturities": "Reconcile cash, current assets/liabilities, near-term maturities, revolver availability, and liquidity runway using real facts plus clearly marked synthetic terms.",
    "Covenant Compliance and Headroom": "Compare each synthetic covenant threshold with the recomputed metric, show headroom, test the relevant period, and flag any breach or missing input.",
    "Risk Rating Assessment": "Recommend a risk rating or change with explicit drivers, evidence, trend direction, and separation of policy judgment from reported facts.",
    "Key Risks and Mitigants": "List material downside risks, their evidence, mitigants, monitoring signals, and residual risk; do not invent management actions.",
    "Recommendation and Conditions": "State approve/maintain/decline/escalate, amount and tenor if applicable, conditions precedent, reporting requirements, and authority required.",
    "Sources and Filing Provenance": "List every filing accession, period, concept/fact reference, source URL, and synthetic input used in the report; distinguish evidence from inference.",
    "Request and Proposed Structure": "Define requested amount, purpose, tenor, pricing, amortization, collateral, covenants, and proposed facility structure from synthetic inputs.",
    "Borrower, Ownership, and Management": "Identify legal borrower, ownership, sponsors/guarantors, management responsibilities, and relevant experience with support for each claim.",
    "Purpose and Sources/Uses": "Reconcile the requested use of funds to total sources, uses, equity contribution, refinancing, and any funding gap.",
    "Business and Industry Analysis": "Connect business model, industry dynamics, competitive position, and downside sensitivities to repayment capacity.",
    "Base and Downside Projections": "Present assumptions, base/downside cases, revenue and margin drivers, debt service, and sensitivity results; mark projections synthetic.",
    "Primary and Secondary Repayment Sources": "Identify operating cash flow as primary repayment and collateral, guarantor support, asset sale, or refinancing as secondary sources with limits.",
    "Leverage, Coverage, and Liquidity": "Combine proposed debt with historical facts and synthetic structure to show leverage, coverage, liquidity, and stress-case headroom.",
    "Collateral and Enterprise Support": "Describe collateral, valuation basis, lien position, guarantees, and enterprise support; identify assumptions requiring approval.",
    "Covenants and Reporting Requirements": "Specify financial/operating covenants, testing dates, reporting packages, cure rights, and source data required for monitoring.",
    "Policy Exceptions": "List each policy exception, rationale, compensating control, approving authority, and unresolved documentation; do not bury exceptions in prose.",
    "Recommendation, Conditions, and Approval Routing": "State the proposed decision, conditions, approval path, delegated authority, and escalation triggers in an executable form.",
    "Existing Exposure and Original Approval": "Reconstruct current exposure, original facility terms, approval date, prior conditions, and performance since approval.",
    "Requested Amendment or Waiver": "Define exactly what term, covenant, payment, or reporting requirement is being amended or waived and for what period.",
    "Cause and Management Explanation": "Summarize the stated cause of the request and management explanation, clearly labeling unverified assertions.",
    "Performance Since Approval": "Compare actual operating and financial performance with the original approval case and prior covenants.",
    "Covenant Breach and Pro Forma Headroom": "Show the breach, calculation, cure status, pro forma result after the amendment, and remaining headroom.",
    "Liquidity, Debt Maturities, and Repayment Capacity": "Test liquidity runway, maturities, cash generation, refinancing needs, and repayment capacity through the requested period.",
    "Pricing, Fees, and Consideration": "State pricing, fees, waiver consideration, amendment economics, and any risk-adjusted compensation.",
    "Downside and Exit Analysis": "Describe downside case, lender protections, collateral/guarantor outcomes, and practical exit or workout path.",
    "Risk Rating Impact": "Explain whether the amendment changes risk rating/classification and tie the conclusion to evidence and policy.",
    "Conditions, Reporting, and Remediation": "List remediation milestones, conditions, reporting cadence, responsible parties, and failure triggers.",
    "Watchlist Trigger and Event Timeline": "Identify the trigger, dates, chronology, source of each event, and why the event meets watchlist criteria.",
    "Current Exposure": "State current funded/unfunded exposure, utilization, collateral, maturity, and risk concentration.",
    "Operating and Financial Trend Analysis": "Show deterioration or improvement in operating, financial, and cash-flow trends across comparable periods.",
    "Liquidity Runway": "Calculate available liquidity and months of runway using explicit cash-burn, availability, and maturity assumptions.",
    "Debt Maturities and Refinancing Risk": "Map maturities, refinancing dependencies, market access assumptions, and contingency actions.",
    "Covenant Forecast": "Forecast covenant metrics over the monitoring horizon, including downside breach timing and headroom.",
    "Management Response": "Record management actions, commitments, dates, and evidence of execution; separate statements from verified outcomes.",
    "Risk Rating or Classification Rationale": "State current/proposed classification and the specific observable facts and policy criteria supporting it.",
    "Monitoring Plan and Cadence": "Define metrics, data sources, owner, review frequency, thresholds, and escalation route.",
    "Lender Action Plan": "Specify immediate lender actions, information requests, approval steps, and contingency actions.",
    "Recommendation": "Give a concise watchlist, continue, restrict, amend, escalate, or exit recommendation with conditions and decision authority.",
}


def _sections(report_type: str, titles: list[str]) -> tuple[ReportSectionSpec, ...]:
    sections = []
    for index, title in enumerate(titles, 1):
        slug = "-".join(title.lower().split())
        sections.append(ReportSectionSpec(
            section_id=f"{report_type}-{index:02d}-{slug}",
            title=title,
            purpose=SECTION_EXPECTATIONS.get(
                title, f"Provide the evidence-grounded {title.lower()} for {report_type}, with source periods and assumptions shown."),
            required_evidence=("filing_fact", "scenario_input"),
            calculations=("recompute_claimed_numbers",),
            required_claims=("state_source_period", "separate_fact_from_inference"),
            forbidden_claims=("unsupported_number", "unstated_filing_period"),
            verifier_ids=(f"REPORT-{report_type}-SECTION-{index:02d}",),
        ))
    return tuple(sections)


def report_specs() -> dict[str, ReportSpec]:
    outlines = {
        "AR": (
            "Annual Review",
            ["Decision Header", "Relationship and Exposure Summary",
             "Borrower and Business Overview", "Industry and Competitive Position",
             "Historical Financial Performance", "Leverage, Coverage, and Cash Flow",
             "Liquidity and Debt Maturities", "Covenant Compliance and Headroom",
             "Risk Rating Assessment", "Key Risks and Mitigants",
             "Recommendation and Conditions", "Sources and Filing Provenance"],
        ),
        "NM": (
            "New-Money Underwriting",
            ["Decision Header", "Request and Proposed Structure",
             "Borrower, Ownership, and Management", "Purpose and Sources/Uses",
             "Business and Industry Analysis", "Historical Financial Performance",
             "Base and Downside Projections", "Primary and Secondary Repayment Sources",
             "Leverage, Coverage, and Liquidity", "Collateral and Enterprise Support",
             "Covenants and Reporting Requirements", "Policy Exceptions",
             "Key Risks and Mitigants", "Recommendation, Conditions, and Approval Routing",
             "Sources and Filing Provenance"],
        ),
        "AW": (
            "Amendment/Waiver",
            ["Decision Header", "Existing Exposure and Original Approval",
             "Requested Amendment or Waiver", "Cause and Management Explanation",
             "Performance Since Approval", "Covenant Breach and Pro Forma Headroom",
             "Liquidity, Debt Maturities, and Repayment Capacity",
             "Pricing, Fees, and Consideration", "Downside and Exit Analysis",
             "Risk Rating Impact", "Conditions, Reporting, and Remediation",
             "Recommendation", "Sources and Filing Provenance"],
        ),
        "WL": (
            "Watchlist/Early Warning",
            ["Decision Header", "Watchlist Trigger and Event Timeline",
             "Current Exposure", "Operating and Financial Trend Analysis",
             "Liquidity Runway", "Debt Maturities and Refinancing Risk",
             "Covenant Forecast", "Management Response",
             "Risk Rating or Classification Rationale", "Monitoring Plan and Cadence",
             "Lender Action Plan", "Recommendation", "Sources and Filing Provenance"],
        ),
    }
    evidence = (
        "selected_filing", "period_end", "revenue", "operating_income",
        "cash", "total_debt", "interest_expense", "synthetic_facility",
    )
    decisions = (
        "use_only_supported_periods", "recompute_ratios_from_facts",
        "escalate_authority_exceptions", "never_fill_missing_facts_by_guess",
    )
    specs = {}
    for code, (title, titles) in outlines.items():
        specs[code] = ReportSpec(
            report_type=code, title=title, sections=_sections(code, titles),
            required_evidence=evidence,
            decision_rules=decisions,
            format_contract={
                "document": "docx",
                "ordered_headings": titles,
                "non_empty_body": True,
                "source_section_required": True,
            },
            verifier_ids=(f"REPORT-{code}-ORDER", f"REPORT-{code}-EVIDENCE",
                          f"REPORT-{code}-ARITHMETIC", f"REPORT-{code}-SOURCES"),
        )
    return specs


def write_report_specs(root: Path) -> list[Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for code, spec in report_specs().items():
        path = root / f"{code}.json"
        path.write_text(json.dumps(spec.to_dict(), indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
