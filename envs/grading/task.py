"""Declarative task spec for grading."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from envs.grading.policy import POLICY_TEXT

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Task:
    task_id: str
    level: int
    seed: int
    prompt: str
    assertions: Path
    submissions: int = 3
    max_steps: int = 200
    use_bundled_fixtures: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    # How many WORLD_AXES (envs/grading/scenario.py) are allowed to land on a
    # harder value; 0 = always the easiest/baseline value per axis. Ignored
    # for bundled-fixture tasks (they don't use the scenario engine).
    difficulty: int = 0


# Track B — thin end-to-end orchestrator (composition / GDE eval).
# Track A training uses per-step prompts in envs/grading/steps.py.
PROMPT = """\
You are a course TA. Grade end to end via inbox (A) and gradescope (B). No SQL —
tools only. Emails can be messy; reconcile before grading.

Compose these steps in order (same policies as the per-step episodes):
  S1 publish a consistent rubric from the latest professor email
  S2 open the Gradescope submission queue
  S3 grade each submission (clarity caps apply) and leave a gradesheet .docx
  S4 resolve every open regrade request

Wrong-student grades are worse than leaving work ungraded. Call finish with a
short summary of real changes only.

{policy}
"""


def _task(task_id: str, level: int, seed: int, submissions: int = 3, *,
          max_steps: int | None = None, bundled: bool = False,
          difficulty: int = 0, tags: tuple[str, ...] = ()) -> Task:
    return Task(
        task_id=task_id,
        level=level,
        seed=seed,
        prompt=PROMPT.format(policy=POLICY_TEXT),
        assertions=FIXTURES / "assertions.sql",
        submissions=submissions,
        max_steps=max_steps if max_steps is not None else max(100, submissions * 40),
        use_bundled_fixtures=bundled,
        difficulty=difficulty,
        tags=tags,
    )


SEED_TASK = _task(
    "GR-SEED-001", level=0, seed=1001, submissions=3, bundled=True,
    tags=("messy_email", "unclear_answer", "handwriting", "regrade_bait",
          "name_collision"),
)

# L1-L3 are difficulty *bands* over WORLD_AXES (envs/grading/scenario.py),
# not just more submissions — difficulty widens how many axes can land on a
# harder value. Each still resolves to one fixed seed/scenario per task_id,
# but that scenario is now sampled from a materially different world each
# time WORLD_AXES grows, rather than three hand-authored fixed worlds.
LADDER = [
    SEED_TASK,
    _task("GR-L0-001", 0, 1001, 3, bundled=True, tags=SEED_TASK.tags),
    _task("GR-L1-001", 1, 2001, max_steps=200, bundled=False, difficulty=1,
          tags=("generated", "difficulty-1")),
    _task("GR-L2-001", 2, 3001, max_steps=260, bundled=False, difficulty=2,
          tags=("generated", "difficulty-2")),
    _task("GR-L3-001", 3, 4001, max_steps=320, bundled=False, difficulty=3,
          tags=("generated", "difficulty-3")),
]

E2E_TASKS: dict[str, Task] = {t.task_id: t for t in LADDER}


def all_tasks() -> dict:
    from envs.grading.steps import make_step_tasks
    out: dict = dict(E2E_TASKS)
    out.update(make_step_tasks(SEED_TASK))
    return out


TASKS: dict[str, Task] = E2E_TASKS
