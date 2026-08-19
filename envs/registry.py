"""Domain registry: resolve task_id prefixes to prepare/make_api/TOOLS."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Domain:
    name: str
    prefix: str
    prepare: Callable
    make_api: Callable
    tools: list
    tasks: dict
    seed_task: Any
    oracle_run: Callable
    oracle_flags: dict
    read_only: set[str]
    prepare_step: Callable | None = None
    step_tasks: Callable | None = None


def _cb():
    from envs.commercial_banking import oracle as cb_oracle
    from envs.commercial_banking.actions import READ_ONLY
    from envs.commercial_banking.runtime import TOOLS, make_api, prepare
    from envs.commercial_banking.steps import make_step_tasks, prepare_step_episode
    from envs.commercial_banking.task import SEED_TASK, all_tasks

    return Domain(
        name="commercial_banking", prefix="CB-",
        prepare=prepare, make_api=make_api, tools=TOOLS,
        tasks=all_tasks(), seed_task=SEED_TASK,
        oracle_run=cb_oracle.run, oracle_flags=cb_oracle.FLAGS,
        read_only=READ_ONLY,
        prepare_step=prepare_step_episode,
        step_tasks=make_step_tasks,
    )


def _gr():
    from envs.grading import oracle as gr_oracle
    from envs.grading.runtime import TOOLS, make_api, prepare
    from envs.grading.steps import make_step_tasks, prepare_step_episode
    from envs.grading.task import SEED_TASK, all_tasks

    return Domain(
        name="grading", prefix="GR-",
        prepare=prepare, make_api=make_api, tools=TOOLS,
        tasks=all_tasks(), seed_task=SEED_TASK,
        oracle_run=gr_oracle.run, oracle_flags=gr_oracle.FLAGS,
        read_only={
            "list_emails", "get_email", "list_assignments", "list_submissions",
            "get_submission", "list_students", "get_rubric",
            "list_regrade_requests", "get_grade",
        },
        prepare_step=prepare_step_episode,
        step_tasks=make_step_tasks,
    )


def _ta():
    """Synthetic visual teaching domain (TA-* tasks)."""
    from envs.teaching import oracle as ta_oracle
    from envs.teaching.runtime import TOOLS, make_api, prepare
    from envs.teaching.task import TASKS, Task

    def _prepare(task, workdir):
        return prepare(task, workdir)[:3]

    def _make_api(path_a, path_b, task, artifacts_dir=None):
        return make_api(task, Path(path_a).parent, artifacts_dir=artifacts_dir)

    return Domain(
        name="teaching", prefix="TA-", prepare=_prepare,
        make_api=_make_api, tools=TOOLS, tasks=TASKS,
        seed_task=TASKS["TA-SEED-001"], oracle_run=ta_oracle.run,
        oracle_flags={}, read_only={
            "search_messages", "get_message", "get_thread", "list_assignments",
            "list_assigned_questions", "list_submissions", "get_submission_pages",
            "get_question", "get_rubric", "get_grades"},
    )


_DOMAINS: dict[str, Domain] | None = None


def domains() -> dict[str, Domain]:
    global _DOMAINS
    if _DOMAINS is None:
        _DOMAINS = {
            "commercial_banking": _cb(),
            "grading": _gr(),
            "teaching": _ta(),
        }
    return _DOMAINS


def all_tasks() -> dict:
    out = {}
    for d in domains().values():
        out.update(d.tasks)
    return out


def resolve(task_id: str) -> Domain:
    # Step episodes look like CB-SEED-001@S1_template
    base = task_id.split("@", 1)[0]
    for d in domains().values():
        if task_id.startswith(d.prefix) or task_id in d.tasks or base in d.tasks:
            return d
    if task_id.startswith("CR-"):
        raise KeyError(
            f"task {task_id!r} belongs to retired credit_ops; use CB-* tasks")
    raise KeyError(f"unknown task_id {task_id!r}")


def prepare_for(task_id: str, workdir: Path) -> tuple[Path, Path, Path, Any]:
    """Prepare DBs for an E2E or step task. Returns paths + task object."""
    domain = resolve(task_id)
    task = domain.tasks[task_id]
    step_id = getattr(task, "step_id", None)
    if step_id and domain.prepare_step is not None:
        parent = domain.tasks[task.parent_task_id]
        pa, pb, assertions = domain.prepare_step(parent, step_id, workdir)
    else:
        pa, pb, assertions = domain.prepare(task, workdir)
    return pa, pb, assertions, task


@dataclass(frozen=True)
class Episode:
    """Everything a caller needs to run one E2E or @step episode.

    The single entry point for `run_baseline`, the Verifiers adapter, and the
    oracle/smoke CLIs — they must all resolve steps, parent-task API knobs,
    and tool allowlists the same way, or their scored criterion counts and
    tool surfaces silently drift apart (P3).
    """

    pa: Path
    pb: Path
    assertions: Path
    task: Any
    api: Any
    tools: list
    step_id: str | None
    max_steps: int


def build_episode(task_id: str, workdir: Path, *,
                   artifacts_dir: Path | None = None) -> Episode:
    """Prepare fixtures, construct the ActionAPI, and filter tools for one task.

    For an `@step` task id this runs the oracle prefix (via `prepare_for`),
    then constructs the ActionAPI against the *parent* E2E task so domain
    knobs (deal_limit_floor, submissions, ...) resolve correctly, and filters
    `domain.tools` down to `task.tool_allowlist` when the task declares one.
    """
    domain = resolve(task_id)
    pa, pb, assertions, task = prepare_for(task_id, workdir)
    step_id = getattr(task, "step_id", None)
    parent_id = getattr(task, "parent_task_id", task_id)
    api_task = domain.tasks.get(parent_id, task)
    api = domain.make_api(pa, pb, api_task, artifacts_dir=artifacts_dir)
    allowlist = getattr(task, "tool_allowlist", None)
    tools = domain.tools
    if allowlist:
        allow = set(allowlist)
        tools = [t for t in domain.tools if t["function"]["name"] in allow]
    return Episode(pa=pa, pb=pb, assertions=assertions, task=task, api=api,
                   tools=tools, step_id=step_id, max_steps=task.max_steps)
