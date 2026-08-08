"""Scripted perfect agent for commercial banking."""
from __future__ import annotations

import difflib
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import verifier  # noqa: E402
from envs.commercial_banking import policy  # noqa: E402
from envs.commercial_banking.actions import ActionAPI  # noqa: E402
from envs.commercial_banking.runtime import make_api, prepare  # noqa: E402
from envs.commercial_banking.task import SEED_TASK, TASKS  # noqa: E402
from envs.commercial_banking.tools import SYSTEM_A, SYSTEM_B  # noqa: E402

FLAGS: dict[str, bool] = {}


def F(k: str) -> bool:
    return bool(FLAGS.get(k))


def _norm(s: str) -> str:
    s = re.sub(r"[.,]", "", (s or "").lower())
    s = re.sub(r"\b(l ?l ?c|inc|corp|corporation|co|company|ltd)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def resolve_customer(api: ActionAPI, name: str, email: str) -> str | None:
    cands = api.search_customers(name)["candidates"]
    live, rejected = [], []
    for c in cands:
        cust = api.get_customer(c["customer_id"])["customer"]
        email_hit = (cust["contact_email"] or "") == email
        name_hit = difflib.SequenceMatcher(
            None, _norm(name), _norm(cust["legal_name"])).ratio() >= 0.85
        if not (email_hit or name_hit):
            continue
        if cust["record_status"] == "active":
            live.append(cust)
        else:
            rejected.append(cust["customer_id"])
    if F("write_archived") and rejected:
        return rejected[0]
    if not live:
        return None
    live.sort(key=lambda c: c["updated_at"], reverse=True)
    master = live[0]
    api.log_action("credit_analyst", "customer_resolved", SYSTEM_B,
                   master["customer_id"],
                   f"Selected live customer; rejected archived {rejected}")
    for d in live[1:]:
        api.request_approval(d["customer_id"], "merge duplicate",
                             f"Live duplicate of {master['customer_id']}")
        api.log_action("credit_analyst", "approval_requested", SYSTEM_B,
                       d["customer_id"], "Live duplicate escalated")
    return master["customer_id"]


def pick_digest(digests: list[dict]) -> dict:
    current = [d for d in digests if d["digest_status"] == "current"]
    pool = current or digests
    if F("use_stale"):
        stale = [d for d in digests if d["digest_status"] == "stale"]
        if stale:
            return stale[0]
    return max(pool, key=lambda d: d["as_of"])


def handle_request(api: ActionAPI, req: dict) -> None:
    rid = req["request_id"]
    rtype = req["request_type"]

    # 1) Template
    templates = api.list_report_templates(rtype)["templates"]
    good = [t for t in templates
            if t["request_type"] == rtype and t["corrupt"] == 0]
    bad = [t for t in templates if t["corrupt"] == 1]
    tpl = (bad[0] if F("use_corrupt_template") and bad else good[0])
    api.select_report_template(rid, tpl["template_id"])
    api.log_action("credit_analyst", "select_template", SYSTEM_A,
                   tpl["template_id"], f"Selected for {rid}")

    # 2) Products / prior deals / covenants
    products = api.list_products()["products"]
    active = [p for p in products
              if p["request_type"] == rtype and p["status"] == "active"]
    matured = [p for p in products
               if p["request_type"] == rtype and p["status"] == "matured"]
    product = (matured[0] if F("use_matured_product") and matured else active[0])
    api.search_prior_deals(req["customer_name"])
    api.log_action("credit_analyst", "search_prior_deals", SYSTEM_A,
                   req["customer_name"], "Reviewed archived deals/materials")
    api.list_covenants(product["product_code"])
    api.log_action("credit_analyst", "list_covenants", SYSTEM_B,
                   product["product_code"], "Pulled active covenants for product")

    # 3) Digests + model
    digests = api.list_web_digests(req["customer_name"])["digests"]
    dig = pick_digest(digests)
    mid = api.create_excel_model(rid, dig["digest_id"])["model_id"]
    lev = policy.leverage(dig["total_debt"], dig["ebitda"])
    api.write_model_cells(
        mid, dig["revenue"], dig["ebitda"], dig["total_debt"],
        dig["interest_expense"], lev)
    api.log_action("credit_analyst", "create_model", SYSTEM_A, mid,
                   f"From digest {dig['digest_id']}; leverage={lev}")

    # 4) Spreading
    job_id = api.submit_to_spreading(rid, mid)["job_id"]
    api.log_action("credit_analyst", "submit_spreading", SYSTEM_A, job_id,
                   "Submitted to spreading team")
    job = api.get_spread_job(job_id)
    lines = {ln["line_key"]: ln["line_value"] for ln in job["lines"]}
    expected = {
        "revenue": dig["revenue"], "ebitda": dig["ebitda"],
        "total_debt": dig["total_debt"],
        "interest_expense": dig["interest_expense"], "leverage": lev,
    }
    mismatches = {k: v for k, v in expected.items()
                  if k in lines and abs(lines[k] - v) > 1e-6}
    if mismatches and not F("skip_spread_check"):
        api.correct_spread_lines(job_id, mismatches)
        api.log_action("credit_analyst", "check_spread", SYSTEM_A, job_id,
                       f"Corrected {list(mismatches)}")
    elif not F("skip_spread_check"):
        api.mark_spread_checked(job_id)
        api.log_action("credit_analyst", "check_spread", SYSTEM_A, job_id,
                       "Lines matched model")

    # 5) Report sections
    sections = tpl["required_sections"].split(",")
    for i, title in enumerate(sections):
        api.write_report_section(
            rid, tpl["template_id"], title,
            f"{title} for {req['customer_name']}: leverage={lev}", i)
    api.log_action("credit_analyst", "write_report", SYSTEM_A, rid,
                   f"Wrote {len(sections)} sections")

    # 6) Customer + push
    cust_id = resolve_customer(api, req["customer_name"], req["customer_email"])
    if cust_id is None:
        api.request_approval(rid, "no live customer", "Cannot push")
        api.log_action("credit_analyst", "approval_requested", SYSTEM_A, rid,
                       "No live customer")
        return

    if req["limit_amount"] > api.deal_limit_floor and not F("ignore_authority"):
        api.request_approval(rid, f"push deal limit {req['limit_amount']}",
                             f"Exceeds floor {api.deal_limit_floor}")
        api.log_action("credit_analyst", "approval_requested", SYSTEM_A, rid,
                       "Limit exceeds authority; not pushed")
        return

    r = api.push_deal_ncino(
        rid, cust_id, product["product_code"], req["limit_amount"],
        tpl["template_id"])
    if not r["ok"]:
        if r["error"]["code"] == "permission_denied":
            api.request_approval(rid, f"push deal limit {req['limit_amount']}",
                                 r["error"]["message"])
            api.log_action("credit_analyst", "approval_requested", SYSTEM_A, rid,
                           "permission_denied on push")
        return
    deal_id = r["deal_id"]
    api.log_action("credit_analyst", "push_deal", SYSTEM_B, deal_id,
                   f"Pushed for {cust_id}")

    # System updates
    for cov in api.list_covenants(product["product_code"])["covenants"]:
        if cov["status"] != "active":
            continue
        if cov["covenant_type"] == "LEVERAGE":
            status = ("compliant" if policy.passes(lev, cov["operator"],
                                                   cov["threshold"])
                      else "breach")
            api.update_system_covenants(deal_id, cov["covenant_id"], lev, status)
    api.update_system_pricing(deal_id, product["rate_bps"], product["fee_bps"])
    api.log_action("credit_analyst", "update_systems", SYSTEM_B, deal_id,
                   "Covenants and pricing updated")


def run(api: ActionAPI) -> None:
    for req in api.list_credit_requests()["requests"]:
        if req["status"] == "open" or True:
            handle_request(api, req)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=SEED_TASK.task_id)
    a = ap.parse_args()
    task = TASKS[a.task]
    work = Path(tempfile.mkdtemp(prefix="sb_cb_oracle_"))
    pa, pb, assertions = prepare(task, work)
    api = make_api(pa, pb, task)
    run(api)
    api.close()
    res = verifier.verify(pa, pb, assertions, domain="commercial_banking",
                          artifacts_dir=pa.parent / "artifacts")
    print(f"oracle  task={task.task_id}  final={res.final:.3f}  raw={res.raw:.3f}")
    print("  by kind: " + "  ".join(
        f"{k}={v[0]:.1f}/{v[1]:.1f}" for k, v in sorted(res.by_kind.items())))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    sys.exit(0 if res.final == 1.0 else 1)
