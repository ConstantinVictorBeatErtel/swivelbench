"""Scripted perfect agent for commercial banking."""
from __future__ import annotations

import difflib
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import verifier  # noqa: E402
from envs.commercial_banking.actions import ActionAPI  # noqa: E402
from envs.commercial_banking.runtime import make_api, prepare  # noqa: E402
from envs.commercial_banking.task import SEED_TASK, TASKS  # noqa: E402

FLAGS: dict[str, bool] = {}


def F(k: str) -> bool:
    return bool(FLAGS.get(k))


def _norm(s: str) -> str:
    s = re.sub(r"[.,]", "", (s or "").lower())
    s = re.sub(r"\b(l ?l ?c|inc|corp|corporation|co|company|ltd)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def resolve_customer(api: ActionAPI, name: str, email: str) -> str | None:
    from envs.commercial_banking.tools import SYSTEM_B
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
    from envs.commercial_banking.steps import run_through
    # run_through reads the first open request; align by ensuring FLAGS apply
    _ = req
    run_through(api)


def run(api: ActionAPI) -> None:
    from envs.commercial_banking.steps import run_through
    run_through(api)


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
    print(
        f"oracle  task={task.task_id}  "
        f"criterion_pass_rate={res.criterion_pass_rate:.3f}  "
        f"task_passed={res.task_passed}"
    )
    print("  by step: " + "  ".join(
        f"{k}={v:.2f}" for k, v in sorted(res.by_step.items())))
    print("  by level: " + "  ".join(
        f"{k}={v:.2f}" for k, v in sorted(res.by_level.items())))
    print(f"  failed: {res.failed or 'NONE'}")
    if res.errors:
        print(f"  SQL ERRORS: {res.errors}")
    sys.exit(0 if res.task_passed else 1)
