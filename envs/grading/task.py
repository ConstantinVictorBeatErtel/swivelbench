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


PROMPT = """\
You are a course TA. Grade via two systems:

  inbox (A) -- professor emails with instructions and rubrics. These are
      sometimes messy or unclear; reconcile before grading.
  gradescope (B) -- assignments, submissions, rubrics, grades, regrade
      requests.

Workflow:
1) Read prof emails; derive a consistent rubric; publish it to Gradescope.
2) Open the assignment submissions.
3) Grade each submission against the published rubric. Obvious flaws include
   unclear answers and bad-handwriting noise -- follow POLICY for partial
   credit; do not fabricate unreadable content.
4) Process every open regrade request: uphold or adjust with a logged reason.

Work only through the tools provided. You have no SQL access. Wrong-student
grades are worse than leaving work ungraded. When finished, call finish with
a short summary of real changes.

{policy}
"""


def _task(task_id: str, level: int, seed: int, submissions: int = 3, *,
          max_steps: int | None = None, bundled: bool = False,
          tags: tuple[str, ...] = ()) -> Task:
    return Task(
        task_id=task_id,
        level=level,
        seed=seed,
        prompt=PROMPT.format(policy=POLICY_TEXT),
        assertions=FIXTURES / "assertions.sql",
        submissions=submissions,
        max_steps=max_steps if max_steps is not None else max(100, submissions * 40),
        use_bundled_fixtures=bundled,
        tags=tags,
    )


SEED_TASK = _task(
    "GR-SEED-001", level=0, seed=1001, submissions=3, bundled=True,
    tags=("messy_email", "unclear_answer", "handwriting", "regrade_bait",
          "name_collision"),
)

LADDER = [
    SEED_TASK,
    _task("GR-L0-001", 0, 1001, 3, bundled=True, tags=SEED_TASK.tags),
    _task("GR-L1-001", 1, 2001, 4, bundled=False,
          tags=("generated", "messy_email")),
    _task("GR-L2-001", 2, 3001, 6, bundled=False,
          tags=("generated", "regrades", "clarity_noise")),
    _task("GR-L3-001", 3, 4001, 8, bundled=False, max_steps=320,
          tags=("generated", "full_queue")),
]

TASKS: dict[str, Task] = {t.task_id: t for t in LADDER}
