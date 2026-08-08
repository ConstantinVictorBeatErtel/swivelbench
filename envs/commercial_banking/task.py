"""Declarative task spec for commercial banking."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from envs.commercial_banking.policy import DEAL_LIMIT_FLOOR, POLICY_TEXT

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Task:
    task_id: str
    level: int
    seed: int
    prompt: str
    assertions: Path
    requests: int = 1
    deal_limit_floor: float = DEAL_LIMIT_FLOOR
    max_steps: int = 200
    use_bundled_fixtures: bool = False
    inject_spread_errors: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)


PROMPT = """\
You are a commercial-banking credit analyst. A customer credit request has
arrived. Work across two systems that do not share keys:

  credit_workbench (A) -- templates, digests, Excel models, spreading queue,
      report drafts.
  ncino_core (B) -- customers, products, covenants, pricing, nCino deals,
      system-of-record updates, audit_log.

Complete each open credit request end to end:
1) Locate and choose the correct report format for this request type.
   Templates can be corrupted; do not use a broken format.
2) Pull current covenants and credit products; pull older deals and materials;
   reason about covenants and pricing.
3) Pull financials from web/news digests; build an Excel model.
4) Submit financials to the spreading team; when results return, check them
   and correct errors before relying on them.
5) Write the report section by section in the chosen format.
6) Push the deal through nCino; update systems that hold covenants and pricing.

Work only through the tools provided. You have no SQL access. Prefer fixing
mess over writing the wrong record. When you are finished, call finish with a
short summary of real changes. Do not claim a change you did not make.

{policy}
"""


def _prompt(floor: float) -> str:
    return PROMPT.format(policy=POLICY_TEXT.format(floor=int(floor)))


def _task(task_id: str, level: int, seed: int, requests: int = 1, *,
          floor: float = DEAL_LIMIT_FLOOR, max_steps: int | None = None,
          bundled: bool = False, inject: bool = True,
          tags: tuple[str, ...] = ()) -> Task:
    return Task(
        task_id=task_id,
        level=level,
        seed=seed,
        prompt=_prompt(floor),
        assertions=FIXTURES / "assertions.sql",
        requests=requests,
        deal_limit_floor=floor,
        max_steps=max_steps if max_steps is not None else max(120, requests * 80),
        use_bundled_fixtures=bundled,
        inject_spread_errors=inject,
        tags=tags,
    )


SEED_TASK = _task(
    "CB-SEED-001", level=0, seed=1001, requests=1, bundled=True,
    tags=("corrupt_template", "spread_inject", "archived_duplicate",
          "stale_digest", "conflicting_digest"),
)

LADDER = [
    SEED_TASK,
    _task("CB-L0-001", 0, 1001, 1, bundled=True,
          tags=SEED_TASK.tags),
    _task("CB-L1-001", 1, 2001, 1, bundled=False,
          tags=("generated", "corrupt_template", "spread_inject")),
    _task("CB-L2-001", 2, 3001, 2, bundled=False, floor=2_000_000,
          tags=("generated", "authority_floor", "multi_request")),
    _task("CB-L3-001", 3, 4001, 3, bundled=False, floor=2_000_000,
          max_steps=400,
          tags=("generated", "full_book", "authority_floor")),
]

TASKS: dict[str, Task] = {t.task_id: t for t in LADDER}
