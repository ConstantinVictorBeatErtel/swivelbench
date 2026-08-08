"""Deterministic seeder for commercial banking generated tasks."""
from __future__ import annotations

import random
from pathlib import Path

from envs.commercial_banking import policy

SCHEMA_A = (Path(__file__).parent / "fixtures" / "_schema_a.sql").read_text()
SCHEMA_B = (Path(__file__).parent / "fixtures" / "_schema_b.sql").read_text()

NAMES = [
    ("Northgate Logistics LLC", "cfo@northgate.example", "94-3177119"),
    ("Cascade Precision Inc", "treasurer@cascade.example", "91-5550100"),
    ("Harborline Marine Co", "finance@harborline.example", "88-2200199"),
    ("Vantage Foods LLC", "cfo@vantage.example", "77-4411220"),
    ("Merrow Industrial Ltd", "ap@merrow.example", "66-9988771"),
]


def generate(*, seed: int, requests: int = 1, floor: float = 5_000_000,
             inject_spread: bool = True, out: Path) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    a_lines = [SCHEMA_A.rstrip(), ""]
    b_lines = [SCHEMA_B.rstrip(), ""]

    # Shared products
    b_lines.append(
        "INSERT INTO credit_products VALUES\n"
        " ('REV-STD', 'revolving_credit', 'Standard Revolver', 'active', 275, 25),\n"
        " ('REV-OLD', 'revolving_credit', 'Legacy Revolver', 'matured', 325, 40),\n"
        " ('TL-STD', 'term_loan', 'Standard Term Loan', 'active', 300, 30);"
    )
    b_lines.append(
        "INSERT INTO covenants VALUES\n"
        " ('COV-LEV', 'REV-STD', 'LEVERAGE', '<=', 4.0, 'active'),\n"
        " ('COV-OLD', 'REV-OLD', 'LEVERAGE', '<=', 3.5, 'retired'),\n"
        " ('COV-TL', 'TL-STD', 'DSCR', '>=', 1.25, 'active');"
    )

    a_lines.append(
        "INSERT INTO report_templates VALUES\n"
        " ('TPL-REV-OK', 'revolving_credit', 'Revolver Credit Memo v3',\n"
        "  'Executive Summary,Financial Analysis,Covenant Review,Recommendation',"
        " 0, NULL),\n"
        " ('TPL-REV-BAD', 'revolving_credit', 'Revolver Credit Memo v2 (corrupt)',\n"
        "  'Executive Summary,Recommendation', 1, 'missing_sections'),\n"
        " ('TPL-TL-OK', 'term_loan', 'Term Loan Memo v1',\n"
        "  'Executive Summary,Collateral,Financial Analysis,Recommendation',"
        " 0, NULL);"
    )

    req_rows, cust_rows, digest_rows, state_rows = [], [], [], []
    expected = []  # for assertions on first request primarily

    for i in range(requests):
        name, email, tin = NAMES[i % len(NAMES)]
        if i >= len(NAMES):
            name = f"{name} {i}"
        rid = f"CRQ-{1001 + i}"
        cid_live = f"CIF-{400 + i}"
        cid_arch = f"CIF-{90 + i}"
        limit = 2_500_000.0 if i == 0 else float(rng.choice(
            [1_500_000, 2_500_000, 6_000_000]))
        ebitda = float(rng.randint(35, 50) * 100_000)
        debt = float(rng.randint(120, 180) * 100_000)
        lev = policy.leverage(debt, ebitda)
        req_rows.append(
            f" ('{rid}', '{name}', '{email}', 'revolving_credit', {limit}, "
            f"'open', 'Credit request {i+1}')")
        state_rows.append(f" ('{rid}', NULL, NULL, NULL, NULL)")
        cust_rows.append(
            f" ('{cid_live}', '{name}', '{tin}', '{email}', 'active', "
            f"'2026-01-20T00:00:00Z')")
        cust_rows.append(
            f" ('{cid_arch}', '{name}, LLC', '{tin.replace('-', '')}', "
            f"'old@{email.split('@')[1]}', 'archived', '2023-06-01T00:00:00Z')")
        dig_cur = f"DIG-C{i}"
        dig_stale = f"DIG-S{i}"
        dig_bad = f"DIG-X{i}"
        digest_rows.append(
            f" ('{dig_cur}', '{name}', 'web', 'current', '2026-01-15', "
            f"42000000.0, {ebitda}, {debt}, 1180000.0)")
        digest_rows.append(
            f" ('{dig_stale}', '{name}', 'news', 'stale', '2024-12-01', "
            f"38000000.0, {ebitda * 0.9}, {debt * 0.9}, 1100000.0)")
        digest_rows.append(
            f" ('{dig_bad}', '{name}', 'news', 'current', '2026-01-10', "
            f"42000000.0, {ebitda * 1.2}, {debt}, 1180000.0)")
        expected.append({
            "request_id": rid, "customer_id": cid_live, "template": "TPL-REV-OK",
            "product": "REV-STD", "leverage": lev, "ebitda": ebitda,
            "limit": limit, "escalate": limit > floor,
            "inject": inject_spread,
        })

    a_lines.append("INSERT INTO credit_requests VALUES\n" + ",\n".join(req_rows) + ";")
    a_lines.append("INSERT INTO request_state VALUES\n" + ",\n".join(state_rows) + ";")
    a_lines.append("INSERT INTO web_digests VALUES\n" + ",\n".join(digest_rows) + ";")
    a_lines.append(
        "INSERT INTO deals_archive VALUES\n"
        " ('ARC-01', 'Northgate Logistics LLC', 'REV-STD', "
        "'LEVERAGE <= 4.0', 'SOFR+275', 2024);"
    )
    b_lines.append("INSERT INTO customers VALUES\n" + ",\n".join(cust_rows) + ";")

    (out / "seed_a.sql").write_text("\n".join(a_lines) + "\n")
    (out / "seed_b.sql").write_text("\n".join(b_lines) + "\n")
    (out / "assertions.sql").write_text(_assertions(expected, floor))


def _assertions(expected: list[dict], floor: float) -> str:
    """Emit multi-facet assertions per request (BTB-inspired coverage)."""
    parts = [
        "-- Generated CB assertions: template/digest/spread/deal/systems facets\n"
    ]
    for i, e in enumerate(expected):
        rid, cid, lev = e["request_id"], e["customer_id"], e["leverage"]
        dig_cur = f"DIG-C{i}"
        dig_stale = f"DIG-S{i}"
        dig_bad = f"DIG-X{i}"
        ebitda = e["ebitda"]
        parts.append(f"""
-- @assert id=P-{rid}-tpl kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.request_state
  WHERE request_id = '{rid}' AND selected_template_id = 'TPL-REV-OK'
);

-- @assert id=N-{rid}-badtpl kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM a.request_state
  WHERE request_id = '{rid}' AND selected_template_id = 'TPL-REV-BAD'
);

-- @assert id=T-{rid}-tpl kind=trail weight=1.0 critical=true
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'select_template' AND target_key = 'TPL-REV-OK'
);

-- @assert id=T-{rid}-priors kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log WHERE action = 'search_prior_deals'
);

-- @assert id=T-{rid}-covs kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'list_covenants' AND target_key = 'REV-STD'
);

-- @assert id=N-{rid}-arch kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals WHERE request_id = '{rid}' AND customer_id LIKE 'CIF-9%'
);
""")
        if e["escalate"]:
            parts.append(f"""
-- @assert id=P-{rid}-esc kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.approval_requests WHERE target = '{rid}'
);

-- @assert id=N-{rid}-nopush kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals WHERE request_id = '{rid}' AND status = 'pushed'
);
""")
        else:
            parts.append(f"""
-- @assert id=P-{rid}-digest kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = '{rid}' AND em.digest_id = '{dig_cur}'
);

-- @assert id=P-{rid}-lev kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.model_cells mc
  JOIN a.request_state rs ON rs.model_id = mc.model_id
  WHERE rs.request_id = '{rid}' AND mc.cell_key = 'leverage'
    AND ABS(mc.cell_value - {lev}) < 1e-9
);

-- @assert id=P-{rid}-spread kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.spread_jobs
  WHERE request_id = '{rid}' AND status = 'checked'
);

-- @assert id=P-{rid}-secs kind=positive weight=1.0
SELECT (
  SELECT COUNT(*) FROM a.report_sections
  WHERE request_id = '{rid}' AND template_id = 'TPL-REV-OK'
    AND section_title IN (
      'Executive Summary', 'Financial Analysis',
      'Covenant Review', 'Recommendation')
) = 4;

-- @assert id=P-{rid}-deal kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = '{rid}' AND customer_id = '{cid}'
    AND product_code = 'REV-STD' AND status = 'pushed'
    AND template_id = 'TPL-REV-OK'
);

-- @assert id=X-{rid}-price kind=propagation weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.system_pricing sp
  JOIN b.deals d ON d.deal_id = sp.deal_id
  WHERE d.request_id = '{rid}' AND sp.rate_bps = 275 AND sp.fee_bps = 25
);

-- @assert id=X-{rid}-cov kind=propagation weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.system_covenants sc
  JOIN b.deals d ON d.deal_id = sc.deal_id
  WHERE d.request_id = '{rid}' AND sc.covenant_id = 'COV-LEV'
    AND ABS(sc.tested_value - {lev}) < 1e-9
);

-- @assert id=X-{rid}-link kind=propagation weight=1.0
SELECT NOT EXISTS (
  SELECT 1
  FROM a.spread_jobs sj
  JOIN a.spread_lines sl ON sl.job_id = sj.job_id
  JOIN a.model_cells mc ON mc.model_id = sj.model_id AND mc.cell_key = sl.line_key
  WHERE sj.request_id = '{rid}' AND sj.status = 'checked'
    AND ABS(sl.line_value - mc.cell_value) > 1e-6
);

-- @assert id=N-{rid}-stale kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = '{rid}' AND em.digest_id = '{dig_stale}'
);

-- @assert id=N-{rid}-conflict kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = '{rid}' AND em.digest_id = '{dig_bad}'
);

-- @assert id=N-{rid}-matured kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = '{rid}' AND product_code = 'REV-OLD'
);

-- @assert id=N-{rid}-retired kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.system_covenants sc
  JOIN b.deals d ON d.deal_id = sc.deal_id
  WHERE d.request_id = '{rid}' AND sc.covenant_id = 'COV-OLD'
);

-- @assert id=T-{rid}-check kind=trail weight=1.0 critical=true
SELECT EXISTS (
  SELECT 1 FROM b.audit_log WHERE action = 'check_spread'
);

-- @assert id=T-{rid}-model kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log WHERE action = 'create_model'
);
""")
            if e.get("inject"):
                parts.append(f"""
-- @assert id=P-{rid}-ebitda-fix kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.spread_lines sl
  JOIN a.spread_jobs sj ON sj.job_id = sl.job_id
  WHERE sj.request_id = '{rid}' AND sl.line_key = 'ebitda'
    AND sl.corrected = 1
    AND ABS(sl.line_value - {ebitda}) < 1e-6
);
""")
    return "\n".join(parts)
