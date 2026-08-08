"""Domain registry: resolve task_id prefixes to prepare/make_api/TOOLS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


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


def _cb():
    from envs.commercial_banking import oracle as cb_oracle
    from envs.commercial_banking.actions import READ_ONLY
    from envs.commercial_banking.runtime import TOOLS, make_api, prepare
    from envs.commercial_banking.task import SEED_TASK, TASKS
    return Domain(
        name="commercial_banking", prefix="CB-",
        prepare=prepare, make_api=make_api, tools=TOOLS,
        tasks=TASKS, seed_task=SEED_TASK,
        oracle_run=cb_oracle.run, oracle_flags=cb_oracle.FLAGS,
        read_only=READ_ONLY,
    )


def _gr():
    from envs.grading import oracle as gr_oracle
    from envs.grading.runtime import TOOLS, make_api, prepare
    from envs.grading.task import SEED_TASK, TASKS
    return Domain(
        name="grading", prefix="GR-",
        prepare=prepare, make_api=make_api, tools=TOOLS,
        tasks=TASKS, seed_task=SEED_TASK,
        oracle_run=gr_oracle.run, oracle_flags=gr_oracle.FLAGS,
        read_only={
            "list_emails", "get_email", "list_assignments", "list_submissions",
            "get_submission", "list_students", "get_rubric",
            "list_regrade_requests", "get_grade",
        },
    )


_DOMAINS: dict[str, Domain] | None = None


def domains() -> dict[str, Domain]:
    global _DOMAINS
    if _DOMAINS is None:
        _DOMAINS = {
            "commercial_banking": _cb(),
            "grading": _gr(),
        }
    return _DOMAINS


def all_tasks() -> dict:
    out = {}
    for d in domains().values():
        out.update(d.tasks)
    return out


def resolve(task_id: str) -> Domain:
    for d in domains().values():
        if task_id.startswith(d.prefix) or task_id in d.tasks:
            return d
    # Legacy CR-* → commercial banking was replaced; point callers clearly.
    if task_id.startswith("CR-"):
        raise KeyError(
            f"task {task_id!r} belongs to retired credit_ops; use CB-* tasks")
    raise KeyError(f"unknown task_id {task_id!r}")
