"""Domain runtime for grading tasks."""
from __future__ import annotations

from pathlib import Path

from core import db
from envs.grading import policy
from envs.grading.actions import ActionAPI
from envs.grading.seeder import generate
from envs.grading.task import Task
from envs.grading.tools import SYSTEM_A, SYSTEM_B, make_tools

FIXTURES = Path(__file__).parent / "fixtures"
TOOLS = make_tools()


def prepare(task: Task, workdir: Path) -> tuple[Path, Path, Path]:
    if task.use_bundled_fixtures:
        fixtures = FIXTURES
        assertions = task.assertions
    else:
        fixtures = workdir / "fixtures"
        generate(seed=task.seed, submissions=task.submissions, out=fixtures)
        assertions = fixtures / "assertions.sql"
    path_a, path_b = db.build(
        workdir, fixtures=fixtures,
        name_a="inbox.db", name_b="gradescope.db",
        seed_a="seed_a.sql", seed_b="seed_b.sql")
    return path_a, path_b, assertions


def make_api(path_a: Path, path_b: Path, task: Task,
             artifacts_dir: Path | None = None) -> ActionAPI:
    art = artifacts_dir or (path_a.parent / "artifacts")
    return ActionAPI(
        path_a, path_b,
        action_codes=policy.ACTION_CODES,
        actor="ta_agent",
        system_a_name=SYSTEM_A,
        system_b_name=SYSTEM_B,
        artifacts_dir=art,
    )
