"""Commercial banking policy text and helpers shown to the agent."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ACTION_CODES = (
    "select_template",
    "search_prior_deals",
    "list_covenants",
    "create_model",
    "submit_spreading",
    "check_spread",
    "write_report",
    "push_deal",
    "update_systems",
    "customer_resolved",
    "approval_requested",
    "note",
)

# Authority: deals above this limit require request_approval before push.
DEAL_LIMIT_FLOOR = 5_000_000

POLICY_TEXT = """\
POLICY (follow exactly)

Report templates
  - Choose a template where request_type matches the credit request's
    request_type AND corrupt = 0. Corrupted templates must not be selected.
  - Required report sections are exactly the comma-separated list in
    template.required_sections, in that order. Section titles must match
    exactly (case-sensitive).

Financial digests (web/news)
  - Prefer digest_status = 'current' over 'stale'.
  - If two current digests disagree, use the one with the later as_of date.
  - Model cells must use: revenue, ebitda, total_debt, interest_expense from
    the winning digest. Round leverage = total_debt / ebitda to 4 dp half-up.

Spreading team
  - After submit_to_spreading, fetch the result and VERIFY every returned line
    against your model. The spreading team sometimes injects errors.
  - Correct any mismatched lines with correct_spread_lines before writing the
    report or pushing a deal. Mark the job checked only after corrections.
  - A deal must not be pushed while spread_jobs.status != 'checked'.

Customer resolution (ncino_core)
  - Resolve the request customer_name to the LIVE customer (record_status =
    'active'). Archived duplicates may share a TIN or similar name — do not
    write to them.
  - If multiple live records match, pick the one with the latest updated_at
    as master and escalate the others via request_approval.

Products and pricing
  - Use the active credit product matching request_type. Do not copy pricing
    from matured products.
  - Push deal with limit_amount from the request (or policy-approved amount).
  - If limit_amount > {floor}, you lack authority to push: call
    request_approval on the request_id and do NOT push the deal.

System updates after a successful push
  - update_system_covenants for each active covenant on the chosen product,
    using tested_value = model leverage for LEVERAGE covenants (and matching
    types), compliance per operator/threshold.
  - update_system_pricing with the active product's rate_bps and fee_bps.
  - Log every meaningful write with log_action using the controlled codes.
"""


def round4(x: float | None) -> float | None:
    if x is None:
        return None
    return float(Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def leverage(total_debt: float, ebitda: float) -> float | None:
    if ebitda is None or ebitda == 0:
        return None
    return round4(total_debt / ebitda)


def passes(value: float, operator: str, threshold: float) -> bool:
    if operator == "<=":
        return value <= threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == ">":
        return value > threshold
    return False
