"""Verifiers adapter for SwivelBench (CB-* and GR-* domains).

Install: `uv pip install verifiers datasets`

Usage:
    from adapters.verifiers import load_environment
    # Prefer Track A step episodes for GRPO training:
    env = load_environment(task_ids=["CB-SEED-001@S1_template"])
"""
from __future__ import annotations

import inspect
import json
import shutil
import tempfile
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _ensure_path() -> None:
    if str(ROOT) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(ROOT))


def _import_vf():
    try:
        import verifiers as vf
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "verifiers is required for the adapter. "
            "Install with: uv pip install 'verifiers>=0.1.0' datasets"
        ) from e
    return vf


def _tool_fns_for(domain, allowlist: set[str] | None = None) -> list[Callable]:
    """Build StatefulToolEnv callables dynamically from domain.tools schemas."""
    fns = []
    for schema in domain.tools:
        name = schema["function"]["name"]
        if allowlist is not None and name not in allowlist:
            continue
        desc = schema["function"]["description"]
        props = schema["function"]["parameters"].get("properties") or {}
        required = schema["function"]["parameters"].get("required") or []

        params = [inspect.Parameter("api", inspect.Parameter.KEYWORD_ONLY)]
        for pname in props:
            default = inspect.Parameter.empty if pname in required else None
            params.insert(-1, inspect.Parameter(
                pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default))

        signature = inspect.Signature(params)

        def _make(n=name, description=desc, signature=signature):
            async def _fn(*args, api: Any = None, **kwargs) -> str:
                if n == "finish":
                    return json.dumps({
                        "ok": True, "acknowledged": True,
                        "summary": kwargs.get("summary", "")})
                prop_names = list(
                    (next(s for s in domain.tools
                          if s["function"]["name"] == n)
                     )["function"]["parameters"].get("properties") or {})
                for i, a in enumerate(args):
                    if i < len(prop_names) and prop_names[i] not in kwargs:
                        kwargs[prop_names[i]] = a
                return json.dumps(getattr(api, n)(**kwargs), default=str)

            _fn.__name__ = n
            _fn.__doc__ = description
            _fn.__signature__ = signature
            return _fn

        fns.append(_make())
    return fns


def load_environment(
    task_ids: list[str] | None = None,
    *,
    critical_cap: float | None = None,  # noqa: ARG001 — ignored (compat)
    max_turns: int | None = None,
    for_training: bool = True,
    prefer_steps: bool = True,
    role_aware_alpha: float = 0.0,
    role_aware_beta: float = 0.0,
):
    """Build a Verifiers StatefulToolEnv over one or more domain tasks.

    RL reward = criterion_pass_rate by default. Pass role_aware_alpha and/or
    role_aware_beta to switch the reward to core.verifier.role_aware_reward
    (ComplexConstraints Eq. 1: required + alpha*bonus - beta*unmet_penalty)
    instead — useful when bonus/penalty-role criteria should shape reward
    differently than an unweighted pass rate. Published pass metric is always
    task_passed, unaffected by either choice.
    By default, when task_ids is None and prefer_steps, loads Track A step
    episodes (better GRPO variance than giant E2E prompts).
    """
    _ensure_path()
    vf = _import_vf()
    from datasets import Dataset

    from core import verifier as vfy
    from envs.registry import all_tasks, build_episode, resolve

    del critical_cap  # no cliff in the new scorer

    tasks_map = all_tasks()
    if task_ids is None:
        if prefer_steps and for_training:
            task_ids = sorted(k for k in tasks_map if "@" in k)
        else:
            task_ids = sorted(k for k in tasks_map if "@" not in k)
    tasks = [tasks_map[t] for t in task_ids]
    domain = resolve(task_ids[0])
    for tid in task_ids[1:]:
        if resolve(tid).name != domain.name:
            raise ValueError(
                "load_environment requires task_ids from a single domain; "
                f"got {task_ids}")

    turns = max_turns if max_turns is not None else max(
        getattr(t, "max_steps", 40) for t in tasks)

    rows = []
    for t in tasks:
        rows.append({
            "prompt": [{"role": "user", "content": t.prompt}],
            "task_id": t.task_id,
            "level": getattr(t, "level", 0),
            "seed": getattr(t, "seed", 0),
            "step_id": getattr(t, "step_id", None),
            "info": {
                "task_id": t.task_id,
                "step_id": getattr(t, "step_id", None),
            },
        })
    dataset = Dataset.from_list(rows)

    # Homogeneous allowlist only when every task shares the same list.
    allowlists = [tuple(getattr(t, "tool_allowlist", ()) or ()) for t in tasks]
    shared_allow = None
    if allowlists and all(a == allowlists[0] for a in allowlists) and allowlists[0]:
        shared_allow = set(allowlists[0])

    class SwivelBenchEnv(vf.StatefulToolEnv):
        def __init__(self, **kwargs):
            kwargs.pop("tools", None)
            super().__init__(tools=[], **kwargs)
            for fn in _tool_fns_for(domain, shared_allow):
                self.add_tool(fn, args_to_skip=["api"])

        async def setup_state(self, state, **kwargs):
            info = state.get("info") or {}
            task_id = (state.get("task_id") or info.get("task_id")
                       or tasks[0].task_id)
            work = Path(tempfile.mkdtemp(prefix=f"sb_vf_{task_id}_"))
            episode = build_episode(task_id, work)
            state["task_id"] = task_id
            state["step_id"] = episode.step_id
            state["domain"] = domain.name
            state["workdir"] = str(work)
            state["path_a"] = str(episode.pa)
            state["path_b"] = str(episode.pb)
            state["assertions"] = str(episode.assertions)
            state["api"] = episode.api
            state["finished"] = False
            return await super().setup_state(state, **kwargs)

        def update_tool_args(self, tool_name, tool_args, messages, state, **kwargs):
            tool_args = dict(tool_args)
            tool_args["api"] = state["api"]
            if tool_name == "finish":
                state["finished"] = True
            return tool_args

        @vf.stop(priority=5)
        async def review_finished(self, state) -> bool:
            return bool(state.get("finished"))

        @vf.cleanup
        async def _cleanup(self, state):
            api = state.get("api")
            if api is not None:
                with suppress(Exception):
                    api.close()
                state["api"] = None
            if "criterion_pass_rate" not in state and state.get("path_a"):
                pa, pb = Path(state["path_a"]), Path(state["path_b"])
                if pa.exists() and pb.exists():
                    res = vfy.verify(
                        pa, pb, Path(state["assertions"]),
                        domain=state.get("domain"),
                        artifacts_dir=pa.parent / "artifacts",
                        step=state.get("step_id"))
                    if role_aware_alpha or role_aware_beta:
                        reward = vfy.role_aware_reward(
                            res, alpha=role_aware_alpha, beta=role_aware_beta)
                    else:
                        reward = res.criterion_pass_rate
                    state["criterion_pass_rate"] = float(reward)
                    state["task_passed"] = bool(res.task_passed)
                    state["reward_detail"] = res.as_dict()
                    # Saturation hint for GRPO group logging
                    state["saturated_hint"] = (
                        res.criterion_pass_rate in (0.0, 1.0))
            work = state.get("workdir")
            if work:
                shutil.rmtree(work, ignore_errors=True)
                state["workdir"] = None

    async def assertion_reward(state, **kwargs) -> float:
        if "criterion_pass_rate" in state:
            return float(state["criterion_pass_rate"])
        api = state.get("api")
        if api is not None:
            with suppress(Exception):
                api.close()
            state["api"] = None
        path_a = Path(state["path_a"])
        path_b = Path(state["path_b"])
        assertions = Path(state["assertions"])
        if not path_a.exists() or not path_b.exists():
            return 0.0
        res = vfy.verify(
            path_a, path_b, assertions,
            domain=state.get("domain"),
            artifacts_dir=path_a.parent / "artifacts",
            step=state.get("step_id"))
        if role_aware_alpha or role_aware_beta:
            reward = vfy.role_aware_reward(
                res, alpha=role_aware_alpha, beta=role_aware_beta)
        else:
            reward = res.criterion_pass_rate
        state["criterion_pass_rate"] = float(reward)
        state["task_passed"] = bool(res.task_passed)
        state["reward_detail"] = res.as_dict()
        state["saturated_hint"] = res.criterion_pass_rate in (0.0, 1.0)
        return float(reward)

    rubric = vf.Rubric(funcs=[assertion_reward])
    return SwivelBenchEnv(
        dataset=dataset,
        eval_dataset=dataset,
        rubric=rubric,
        max_turns=turns,
        env_id=f"swivelbench/{domain.name}",
    )
