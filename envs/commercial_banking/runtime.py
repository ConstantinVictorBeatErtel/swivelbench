"""Domain runtime: build DBs and ActionAPI for commercial banking tasks."""
from __future__ import annotations

from pathlib import Path

from core import db
from envs.commercial_banking import policy
from envs.commercial_banking.actions import ActionAPI
from envs.commercial_banking.seeder import generate
from envs.commercial_banking.task import Task
from envs.commercial_banking.tools import SYSTEM_A, SYSTEM_B, make_tools

FIXTURES = Path(__file__).parent / "fixtures"
TOOLS = make_tools()


def prepare(task: Task, workdir: Path) -> tuple[Path, Path, Path]:
    if task.use_bundled_fixtures:
        fixtures = FIXTURES
        assertions = task.assertions
    else:
        fixtures = workdir / "fixtures"
        generate(seed=task.seed, requests=task.requests,
                 floor=task.deal_limit_floor,
                 inject_spread=task.inject_spread_errors, out=fixtures)
        assertions = fixtures / "assertions.sql"
    path_a, path_b = db.build(
        workdir, fixtures=fixtures,
        name_a="credit_workbench.db", name_b="ncino_core.db",
        seed_a="seed_a.sql", seed_b="seed_b.sql")
    return path_a, path_b, assertions


def make_api(path_a: Path, path_b: Path, task: Task,
             artifacts_dir: Path | None = None) -> ActionAPI:
    art = artifacts_dir or (path_a.parent / "artifacts")
    return ActionAPI(
        path_a, path_b,
        action_codes=policy.ACTION_CODES,
        actor="credit_analyst",
        system_a_name=SYSTEM_A,
        system_b_name=SYSTEM_B,
        deal_limit_floor=task.deal_limit_floor,
        force_spread_inject=task.inject_spread_errors,
        artifacts_dir=art,
    )
