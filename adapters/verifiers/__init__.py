"""Verifiers adapter for SwivelBench (CB-* and GR-* domains).

Install: `uv pip install verifiers datasets`

Usage:
    from adapters.verifiers import load_environment
    env = load_environment(task_ids=["CB-SEED-001", "GR-SEED-001"])
"""
from __future__ import annotations

import inspect
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

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


def _tool_fns_for(domain) -> list[Callable]:
    """Build StatefulToolEnv callables dynamically from domain.tools schemas."""
    fns = []
    for schema in domain.tools:
        name = schema["function"]["name"]
        desc = schema["function"]["description"]
        props = schema["function"]["parameters"].get("properties") or {}
        required = schema["function"]["parameters"].get("required") or []

        # Build a function with explicit kwargs matching the schema.
        params = [inspect.Parameter("api", inspect.Parameter.KEYWORD_ONLY)]
        for pname in props:
            default = inspect.Parameter.empty if pname in required else None
            params.insert(-1, inspect.Parameter(
                pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default))

        def _make(n=name):
            async def _fn(*args, api: Any = None, **kwargs) -> str:
                if n == "finish":
                    return json.dumps({
                        "ok": True, "acknowledged": True,
                        "summary": kwargs.get("summary", "")})
                # Bind positional if any slipped through
                prop_names = list(
                    (next(s for s in domain.tools
                          if s["function"]["name"] == n)
                     )["function"]["parameters"].get("properties") or {})
                for i, a in enumerate(args):
                    if i < len(prop_names) and prop_names[i] not in kwargs:
                        kwargs[prop_names[i]] = a
                return json.dumps(getattr(api, n)(**kwargs), default=str)

            _fn.__name__ = n
            _fn.__doc__ = desc
            _fn.__signature__ = inspect.Signature(params)
            return _fn

        fns.append(_make())
    return fns


def load_environment(
    task_ids: list[str] | None = None,
    *,
    critical_cap: float | None = None,
    max_turns: int | None = None,
    for_training: bool = True,
):
    """Build a Verifiers StatefulToolEnv over one or more domain tasks."""
    _ensure_path()
    vf = _import_vf()
    from datasets import Dataset

    from core import verifier as vfy
    from envs.registry import all_tasks, resolve

    tasks_map = all_tasks()
    if task_ids is None:
        task_ids = list(tasks_map.keys())
    tasks = [tasks_map[t] for t in task_ids]
    # Homogeneous tools: all task_ids must share a domain.
    domain = resolve(task_ids[0])
    for tid in task_ids[1:]:
        if resolve(tid).name != domain.name:
            raise ValueError(
                "load_environment requires task_ids from a single domain; "
                f"got {task_ids}")

    cap = critical_cap if critical_cap is not None else (
        None if for_training else vfy.CRITICAL_CAP)
    turns = max_turns if max_turns is not None else max(t.max_steps for t in tasks)

    rows = []
    for t in tasks:
        rows.append({
            "prompt": [{"role": "user", "content": t.prompt}],
            "task_id": t.task_id,
            "level": t.level,
            "seed": t.seed,
            "info": {"task_id": t.task_id},
        })
    dataset = Dataset.from_list(rows)

    class SwivelBenchEnv(vf.StatefulToolEnv):
        def __init__(self, **kwargs):
            kwargs.pop("tools", None)
            super().__init__(tools=[], **kwargs)
            for fn in _tool_fns_for(domain):
                self.add_tool(fn, args_to_skip=["api"])

        async def setup_state(self, state, **kwargs):
            info = state.get("info") or {}
            task_id = (state.get("task_id") or info.get("task_id")
                       or tasks[0].task_id)
            task = domain.tasks[task_id]
            work = Path(tempfile.mkdtemp(prefix=f"sb_vf_{task_id}_"))
            path_a, path_b, assertions = domain.prepare(task, work)
            api = domain.make_api(path_a, path_b, task)
            state["task_id"] = task_id
            state["workdir"] = str(work)
            state["path_a"] = str(path_a)
            state["path_b"] = str(path_b)
            state["assertions"] = str(assertions)
            state["api"] = api
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
                try:
                    api.close()
                except Exception:  # noqa: BLE001
                    pass
                state["api"] = None
            if "final_score" not in state and state.get("path_a"):
                pa, pb = Path(state["path_a"]), Path(state["path_b"])
                if pa.exists() and pb.exists():
                    res = vfy.verify(pa, pb, Path(state["assertions"]),
                                     critical_cap=cap)
                    state["final_score"] = float(res.final)
                    state["reward_detail"] = res.as_dict()
            work = state.get("workdir")
            if work:
                shutil.rmtree(work, ignore_errors=True)
                state["workdir"] = None

    async def assertion_reward(state, **kwargs) -> float:
        if "final_score" in state:
            return float(state["final_score"])
        api = state.get("api")
        if api is not None:
            try:
                api.close()
            except Exception:  # noqa: BLE001
                pass
            state["api"] = None
        path_a = Path(state["path_a"])
        path_b = Path(state["path_b"])
        assertions = Path(state["assertions"])
        if not path_a.exists() or not path_b.exists():
            return 0.0
        res = vfy.verify(path_a, path_b, assertions, critical_cap=cap)
        state["final_score"] = float(res.final)
        state["reward_detail"] = res.as_dict()
        return float(res.final)

    rubric = vf.Rubric(funcs=[assertion_reward])
    return SwivelBenchEnv(
        dataset=dataset,
        eval_dataset=dataset,
        rubric=rubric,
        max_turns=turns,
        env_id=f"swivelbench/{domain.name}",
    )
