"""Generate the structured commercial-credit scenario corpus from SEC facts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reports import report_specs
from .sec import COMPANIES

REPORT_TYPES = ("AR", "NM", "AW", "WL")
VARIANTS = ("BASE", "REC", "ADV")


def _facts_by_metric(sec_root: Path, ticker: str) -> dict[str, list[dict[str, Any]]]:
    path = Path(sec_root) / "normalized" / "sec_facts.jsonl"
    result: dict[str, list[dict[str, Any]]] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("company_id") != COMPANIES[ticker]["company_id"]:
            continue
        metric = row["fact_id"].split(":", 2)[1]
        result.setdefault(metric, []).append(row)
    for rows in result.values():
        rows.sort(key=lambda row: (row.get("end_date") or row.get("instant_date") or "", row.get("filed_date", "")), reverse=True)
    return result


def _latest(facts: dict[str, list[dict[str, Any]]], metric: str) -> dict[str, Any] | None:
    return facts.get(metric, [None])[0]


def _real_evidence(ticker: str, facts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    metrics = {}
    for metric in ("revenue", "operating_income", "net_income", "cash", "current_assets",
                   "current_liabilities", "assets", "long_term_debt", "interest_expense",
                   "operating_cash_flow", "capex", "equity"):
        fact = _latest(facts, metric)
        if fact:
            metrics[metric] = fact
    return {"company": ticker, "metrics": metrics,
            "source_rule": "every number is traceable to its SecFact source_artifact and accession"}


def _derived(real: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    values = {key: row.get("value") for key, row in real["metrics"].items()}
    debt = values.get("long_term_debt")
    cash = values.get("cash")
    operating_income = values.get("operating_income")
    interest = values.get("interest_expense")
    revenue = values.get("revenue")
    facility = overlay["facility_amount"]
    total_debt = (float(debt) if isinstance(debt, (int, float)) else 0.0) + facility
    result: dict[str, Any] = {"total_debt": total_debt}
    if isinstance(cash, (int, float)):
        result["net_debt"] = total_debt - float(cash)
    if isinstance(operating_income, (int, float)) and isinstance(interest, (int, float)) and interest:
        result["interest_coverage"] = float(operating_income) / abs(float(interest))
    if isinstance(revenue, (int, float)) and revenue:
        result["operating_margin"] = float(operating_income or 0) / float(revenue)
    result["formula_version"] = "swivelbench-credit-formulas.v1"
    return result


def generate_banking(root: Path, *, sec_root: Path = Path("data/banking/sec")) -> dict[str, int]:
    root = Path(root)
    scenarios_root, gold_root, references_root = root / "scenarios", root / "gold", root / "references"
    for directory in (scenarios_root, gold_root, references_root):
        directory.mkdir(parents=True, exist_ok=True)
    specs = report_specs()
    scenario_count = gold_count = reference_count = 0
    task_ids: list[str] = []
    for ticker in COMPANIES:
        facts = _facts_by_metric(sec_root, ticker)
        real = _real_evidence(ticker, facts)
        for report_type in REPORT_TYPES:
            reference_id = f"CB-PUB-{ticker}-{report_type}-REFERENCE"
            reference = {
                "schema": "swivelbench.credit-reference.v1", "reference_id": reference_id,
                "company": ticker, "report_type": report_type,
                "sections": [{"title": section.title,
                              "body": f"Evidence-grounded placeholder for {section.title}; cite filing facts and separate synthetic overlay."}
                             for section in specs[report_type].sections],
                "source_ids": [row["fact_id"] for row in real["metrics"].values()],
            }
            (references_root / f"{ticker}-{report_type}.json").write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
            (references_root / f"{ticker}-{report_type}.md").write_text(
                f"# {specs[report_type].title}: {ticker}\n\n" +
                "\n".join(f"## {section.title}\n\nEvidence-grounded reference placeholder.\n" for section in specs[report_type].sections),
                encoding="utf-8")
            reference_count += 1
            for variant in VARIANTS:
                task_id = f"CB-PUB-{ticker}-{report_type}-{variant}"
                task_ids.append(task_id)
                overlay = {
                    "facility_amount": 25_000_000 if variant == "BASE" else 30_000_000,
                    "interest_rate_bps": 250 if variant == "BASE" else 325,
                    "covenant_leverage_limit": 4.5 if report_type != "WL" else 4.0,
                    "synthetic": True,
                }
                if variant == "REC":
                    overlay.update({"reconciliation_challenge": "amended_or_stale_period",
                                    "authority_required": "reconcile_latest_authoritative_filing"})
                elif variant == "ADV":
                    overlay.update({"adversarial_challenge": "instruction_or_template_distractor",
                                    "authority_required": "escalate_policy_exception"})
                scenario = {
                    "schema": "swivelbench.credit-scenario.v1", "task_id": task_id,
                    "company": ticker, "company_id": COMPANIES[ticker]["company_id"],
                    "split": COMPANIES[ticker]["split"], "report_type": report_type,
                    "variant": variant, "report_spec_ref": f"reports/specs/{report_type}.json",
                    "real_sec_evidence": real, "synthetic_lending_overlay": overlay,
                    "public_source_ids": [row["fact_id"] for row in real["metrics"].values()],
                }
                gold = {
                    "schema": "swivelbench.credit-gold.v1", "task_id": task_id,
                    "derived_metrics": _derived(real, overlay),
                    "expected_decision": "maintain_and_monitor" if variant == "BASE" else "reconcile_and_escalate",
                    "required_sections": [section.title for section in specs[report_type].sections],
                    "required_verifiers": list(specs[report_type].verifier_ids),
                    "variant_rule": "BASE uses ordinary authority; REC requires source reconciliation; ADV requires authority escalation.",
                }
                (scenarios_root / f"{task_id}.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
                (gold_root / f"{task_id}.json").write_text(json.dumps(gold, indent=2) + "\n", encoding="utf-8")
                scenario_count += 1
                gold_count += 1
    summary = {"companies": len(COMPANIES), "report_types": 4, "variants": 3,
               "scenarios": scenario_count, "gold": gold_count, "references": reference_count}
    (root / "release-counts.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (root / "task-manifest.json").write_text(json.dumps({
        "schema": "swivelbench.task-manifest.v1", "domain": "banking",
        "task_ids": task_ids, "public_root": "scenarios", "private_root": "gold",
    }, indent=2) + "\n", encoding="utf-8")
    return summary


def validate_banking(root: Path) -> dict[str, Any]:
    root = Path(root)
    scenarios = sorted((root / "scenarios").glob("*.json"))
    gold = sorted((root / "gold").glob("*.json"))
    references = sorted((root / "references").glob("*.json"))
    issues: list[str] = []
    if len(scenarios) != 240:
        issues.append(f"expected 240 scenarios, found {len(scenarios)}")
    if len(gold) != 240:
        issues.append(f"expected 240 gold files, found {len(gold)}")
    if len(references) != 80:
        issues.append(f"expected 80 references, found {len(references)}")
    task_manifest = root / "task-manifest.json"
    if task_manifest.is_file() and len(json.loads(task_manifest.read_text(encoding="utf-8")).get("task_ids", [])) != 240:
        issues.append("banking task manifest count mismatch")
    for path in scenarios:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "expected_decision" in payload or "derived_metrics" in payload:
            issues.append(f"public scenario leaks gold: {path.name}")
        if not payload.get("real_sec_evidence", {}).get("metrics"):
            issues.append(f"scenario has no SEC evidence: {path.name}")
    return {"ok": not issues, "scenarios": len(scenarios), "gold": len(gold),
            "references": len(references), "issues": issues}
