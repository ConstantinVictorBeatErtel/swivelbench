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


# Track B — thin end-to-end orchestrator (composition / GDE eval).
# Track A training uses per-step prompts in envs/commercial_banking/steps.py.
PROMPT = """\
You are a commercial-banking credit analyst. Complete each open credit request
end to end across credit_workbench (A) and ncino_core (B). Systems do not share
keys. No SQL — tools only.

Compose these steps in order (same policies as the per-step episodes):
  S1 choose a non-corrupt report template
  S2 pull products, prior deals, covenants
  S3 build Excel model from the current digest
  S4 submit/check/correct spreading
  S5 write the credit memo .docx
  S6 resolve the live customer and push the nCino deal
  S7 update covenants and pricing

Formatting is graded (real .xlsx / .docx). Prefer fixing mess over writing the
wrong record. Call finish with a short summary of real changes only.

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

E2E_TASKS: dict[str, Task] = {t.task_id: t for t in LADDER}


def all_tasks() -> dict:
    """E2E ladder plus Track A step episodes on the seed task."""
    from envs.commercial_banking.steps import make_step_tasks
    out: dict = dict(E2E_TASKS)
    out.update(make_step_tasks(SEED_TASK))
    return out


TASKS: dict[str, Task] = E2E_TASKS  # backward-compat: E2E only
