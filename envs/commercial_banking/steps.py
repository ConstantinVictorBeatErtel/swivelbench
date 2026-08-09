"""Per-step commercial-banking prompts and oracle step runners (Track A)."""
from __future__ import annotations

from pathlib import Path

from core.steps import StepSpec, StepTask
from envs.commercial_banking import policy as pol
from envs.commercial_banking.actions import ActionAPI
from envs.commercial_banking.oracle import (
    F,
    pick_digest,
    resolve_customer,
)
from envs.commercial_banking.runtime import make_api, prepare
from envs.commercial_banking.task import SEED_TASK, Task
from envs.commercial_banking.tools import SYSTEM_A, SYSTEM_B

# Fair, self-contained step prompts (no prior agent transcript).
STEP_SPECS: dict[str, StepSpec] = {
    "S1_template": StepSpec(
        step_id="S1_template",
        title="Choose report template",
        max_steps=20,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "list_report_templates", "select_report_template",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

Systems: credit_workbench (A) and ncino_core (B). No SQL. Use tools only.

Job (S1 — choose report template):
  For the open credit request, list report templates for its request_type and
  select a non-corrupt template. Log select_template with the chosen id.

Graded checklist (all must pass for task_passed):
  - P1: selected_template_id is the good revolving template (TPL-REV-OK on seed)
  - N1: do not select a corrupt template
  - T1: audit_log has select_template for the good template

Discoverability: template.corrupt is visible via list_report_templates.
Do not invent template ids. Call finish when done.
""",
    ),
    "S2_products": StepSpec(
        step_id="S2_products",
        title="Products, prior deals, covenants",
        max_steps=30,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "list_products", "search_prior_deals", "list_covenants",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

Prior workflow state is already prepared. Do not re-select templates.

Job (S2 — products / prior deals / covenants):
  Identify the active product for this request type, search prior deals for
  the customer name, and list covenants for that product. Log both searches.

Graded checklist:
  - T9: audit_log has search_prior_deals
  - T10: audit_log has list_covenants for the active product (REV-STD on seed)

Prefer active products over matured. Call finish when done.
""",
    ),
    "S3_model": StepSpec(
        step_id="S3_model",
        title="Digests → Excel model",
        max_steps=40,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "list_web_digests", "create_excel_model", "write_model_cells",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

Job (S3 — digests → Excel model):
  Pull web/news digests for the customer. Prefer digest_status=current (never
  stale or conflicting). Create an Excel model and write revenue, ebitda,
  total_debt, interest_expense, and leverage (total_debt/ebitda, 4 dp).

Graded checklist:
  - P2/P6/P7: model cells match the current digest; leverage correct
  - N6/N7: do not use DIG-STALE or DIG-CONFLICT
  - T6: audit create_model
  - F1: real .xlsx with Model sheet and Field/Value rows

Call finish when done.
""",
    ),
    "S4_spreading": StepSpec(
        step_id="S4_spreading",
        title="Spreading submit / check / correct",
        max_steps=40,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "get_excel_model", "submit_to_spreading", "get_spread_job",
            "correct_spread_lines", "mark_spread_checked",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

An Excel model already exists for the open request.

Job (S4 — spreading):
  Submit the model to spreading, inspect returned lines, correct any injected
  errors so lines match the model, and mark the job checked. Log submit and check.

Graded checklist:
  - P3/P9/X3/X4: spread checked; ebitda corrected; lines match model
  - N5: never leave a pushed deal with unchecked spread (invariant)
  - T2/T7: audit check_spread and submit_spreading

Call finish when done.
""",
    ),
    "S5_report": StepSpec(
        step_id="S5_report",
        title="Write credit memo sections",
        max_steps=40,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "list_report_templates", "write_report_section",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

Template and model/spread state are already prepared.

Job (S5 — write report):
  Write all required sections for the selected good template as a real .docx
  credit memo. Log write_report.

Graded checklist:
  - P4/P8/X5: four required sections under TPL-REV-OK matching selection
  - N4: no sections under the corrupt template
  - T8: audit write_report
  - F2: real .docx with headings in order and non-empty bodies

Call finish when done.
""",
    ),
    "S6_customer_push": StepSpec(
        step_id="S6_customer_push",
        title="Resolve customer and push nCino deal",
        max_steps=40,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "search_customers", "get_customer", "list_products",
            "push_deal_ncino", "request_approval",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

Template, model, spread, and report are already prepared.

Job (S6 — customer + push):
  Resolve the live (non-archived) customer, choose the active product, and
  push the nCino deal within authority. Log customer_resolved and push_deal.

Graded checklist:
  - P5/P10: deal pushed for CIF-417 / REV-STD / TPL-REV-OK with correct limit
  - N2/N3: not archived CIF-092; not matured REV-OLD
  - T3/T5: audit push_deal and customer_resolved

Call finish when done.
""",
    ),
    "S7_systems": StepSpec(
        step_id="S7_systems",
        title="Update covenants and pricing",
        max_steps=30,
        tool_allowlist=(
            "list_credit_requests", "get_credit_request",
            "list_covenants", "list_deals",
            "update_system_covenants", "update_system_pricing",
            "log_action", "finish",
        ),
        prompt="""\
You are a commercial-banking credit analyst. THIS EPISODE IS ONE STEP ONLY.

A pushed deal already exists.

Job (S7 — systems update):
  Update system covenants (active LEVERAGE with tested leverage) and pricing
  from the active product. Log update_systems. Do not write retired covenants.

Graded checklist:
  - X1/X2: pricing 275/25; COV-LEV tested at 3.7590 compliant
  - N8: do not write COV-OLD
  - T4: audit update_systems

Call finish when done.
""",
    ),
}

STEP_ORDER = list(STEP_SPECS.keys())


def _req(api: ActionAPI) -> dict:
    return api.list_credit_requests()["requests"][0]


def step_S1_template(api: ActionAPI, req: dict | None = None) -> dict:
    if not isinstance(req, dict) or "request_id" not in (req or {}):
        req = _req(api)
    rid, rtype = req["request_id"], req["request_type"]
    templates = api.list_report_templates(rtype)["templates"]
    good = [t for t in templates if t["request_type"] == rtype and t["corrupt"] == 0]
    bad = [t for t in templates if t["corrupt"] == 1]
    tpl = (bad[0] if F("use_corrupt_template") and bad else good[0])
    api.select_report_template(rid, tpl["template_id"])
    api.log_action("credit_analyst", "select_template", SYSTEM_A,
                   tpl["template_id"], f"Selected for {rid}")
    return {"req": req, "tpl": tpl}


def step_S2_products(api: ActionAPI, ctx: dict) -> dict:
    req, rtype = ctx["req"], ctx["req"]["request_type"]
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
    ctx["product"] = product
    return ctx


def step_S3_model(api: ActionAPI, ctx: dict) -> dict:
    req = ctx["req"]
    digests = api.list_web_digests(req["customer_name"])["digests"]
    dig = pick_digest(digests)
    mid = api.create_excel_model(req["request_id"], dig["digest_id"])["model_id"]
    lev = pol.leverage(dig["total_debt"], dig["ebitda"])
    api.write_model_cells(
        mid, dig["revenue"], dig["ebitda"], dig["total_debt"],
        dig["interest_expense"], lev)
    api.log_action("credit_analyst", "create_model", SYSTEM_A, mid,
                   f"From digest {dig['digest_id']}; leverage={lev}")
    ctx["dig"] = dig
    ctx["mid"] = mid
    ctx["lev"] = lev
    return ctx


def step_S4_spreading(api: ActionAPI, ctx: dict) -> dict:
    req, mid, dig, lev = ctx["req"], ctx["mid"], ctx["dig"], ctx["lev"]
    job_id = api.submit_to_spreading(req["request_id"], mid)["job_id"]
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
    ctx["job_id"] = job_id
    return ctx


def step_S5_report(api: ActionAPI, ctx: dict) -> dict:
    req, tpl, lev = ctx["req"], ctx["tpl"], ctx["lev"]
    sections = tpl["required_sections"].split(",")
    for i, title in enumerate(sections):
        api.write_report_section(
            req["request_id"], tpl["template_id"], title,
            f"{title} for {req['customer_name']}: leverage={lev}", i)
    api.log_action("credit_analyst", "write_report", SYSTEM_A, req["request_id"],
                   f"Wrote {len(sections)} sections")
    return ctx


def step_S6_customer_push(api: ActionAPI, ctx: dict) -> dict:
    req, tpl, product = ctx["req"], ctx["tpl"], ctx["product"]
    cust_id = resolve_customer(api, req["customer_name"], req["customer_email"])
    if cust_id is None:
        api.request_approval(req["request_id"], "no live customer", "Cannot push")
        api.log_action("credit_analyst", "approval_requested", SYSTEM_A,
                       req["request_id"], "No live customer")
        return ctx
    if req["limit_amount"] > api.deal_limit_floor and not F("ignore_authority"):
        api.request_approval(req["request_id"], f"push deal limit {req['limit_amount']}",
                             f"Exceeds floor {api.deal_limit_floor}")
        api.log_action("credit_analyst", "approval_requested", SYSTEM_A,
                       req["request_id"], "Limit exceeds authority; not pushed")
        return ctx
    r = api.push_deal_ncino(
        req["request_id"], cust_id, product["product_code"], req["limit_amount"],
        tpl["template_id"])
    if not r["ok"]:
        return ctx
    deal_id = r["deal_id"]
    api.log_action("credit_analyst", "push_deal", SYSTEM_B, deal_id,
                   f"Pushed for {cust_id}")
    ctx["deal_id"] = deal_id
    ctx["cust_id"] = cust_id
    return ctx


def step_S7_systems(api: ActionAPI, ctx: dict) -> dict:
    # An authority escalation is a valid terminal branch for this request;
    # there is no deal whose systems can be updated in that case.
    deal_id = ctx.get("deal_id")
    if not deal_id:
        return ctx
    product, lev = ctx["product"], ctx["lev"]
    for cov in api.list_covenants(product["product_code"])["covenants"]:
        if cov["status"] != "active":
            continue
        if cov["covenant_type"] == "LEVERAGE":
            status = ("compliant" if pol.passes(lev, cov["operator"],
                                                   cov["threshold"])
                      else "breach")
            api.update_system_covenants(deal_id, cov["covenant_id"], lev, status)
    api.update_system_pricing(deal_id, product["rate_bps"], product["fee_bps"])
    api.log_action("credit_analyst", "update_systems", SYSTEM_B, deal_id,
                   "Covenants and pricing updated")
    return ctx


ORACLE_STEPS = {
    "S1_template": step_S1_template,
    "S2_products": step_S2_products,
    "S3_model": step_S3_model,
    "S4_spreading": step_S4_spreading,
    "S5_report": step_S5_report,
    "S6_customer_push": step_S6_customer_push,
    "S7_systems": step_S7_systems,
}


def run_one_request(api: ActionAPI, req: dict,
                    through_step: str | None = None) -> dict:
    """Run oracle steps for a single credit request."""
    ctx: dict = {"req": req}
    for sid in STEP_ORDER:
        fn = ORACLE_STEPS[sid]
        ctx = fn(api, req) if sid == "S1_template" else fn(api, ctx)
        if through_step is not None and sid == through_step:
            break
    return ctx


def run_through(api: ActionAPI, through_step: str | None = None) -> dict:
    """Run oracle steps for every listed credit request (E2E or prefix)."""
    ctx: dict = {}
    for req in api.list_credit_requests()["requests"]:
        ctx = run_one_request(api, req, through_step=through_step)
    return ctx


def prepare_step_episode(task: Task, step_id: str, workdir: Path
                         ) -> tuple[Path, Path, Path]:
    """Build DBs, run oracle for all steps *before* step_id, return paths."""
    if step_id not in STEP_SPECS:
        raise KeyError(step_id)
    idx = STEP_ORDER.index(step_id)
    prefix = STEP_ORDER[:idx]
    pa, pb, assertions = prepare(task, workdir)
    api = make_api(pa, pb, task)
    try:
        if prefix:
            run_through(api, through_step=prefix[-1])
    finally:
        api.close()
    return pa, pb, assertions


def make_step_tasks(parent: Task = SEED_TASK) -> dict[str, StepTask]:
    out: dict[str, StepTask] = {}
    for sid, spec in STEP_SPECS.items():
        tid = f"{parent.task_id}@{sid}"
        out[tid] = StepTask(
            task_id=tid,
            parent_task_id=parent.task_id,
            step_id=sid,
            level=parent.level,
            seed=parent.seed,
            prompt=spec.prompt,
            assertions=parent.assertions,
            max_steps=spec.max_steps,
            domain="commercial_banking",
            use_bundled_fixtures=parent.use_bundled_fixtures,
            tags=parent.tags + ("step", sid),
            requests=parent.requests,
            deal_limit_floor=parent.deal_limit_floor,
            inject_spread_errors=parent.inject_spread_errors,
            tool_allowlist=spec.tool_allowlist,
        )
    return out
