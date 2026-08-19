"""Baseline runner. Rolls models out against a domain via OpenRouter.

  OPENROUTER_API_KEY=... python3 -m eval.run_baseline --models qwen/qwen3-8b \\
      --task CB-SEED-001 -k 3
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI  # noqa: E402

from core import verifier  # noqa: E402
from envs.registry import build_episode, resolve  # noqa: E402

OUT = Path(__file__).parent / "results"
RUNS = OUT / "runs"


def rollout(client: OpenAI, model: str, task, domain, idx: int,
            *, keep: bool, max_steps: int | None = None,
            max_completion_tokens: int | None = None,
            request_interval_seconds: float = 0.0) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_model = model.replace("/", "_").replace(":", "_")
    run_id = f"{task.task_id}_{safe_model}_r{idx}_{stamp}"
    work = RUNS / run_id if keep else Path(tempfile.mkdtemp(prefix=f"sb_{idx}_"))
    if keep:
        work.mkdir(parents=True, exist_ok=True)
    art = work / "artifacts"
    t0 = time.time()
    try:
        episode = build_episode(task.task_id, work, artifacts_dir=art)
        pa, pb, assertions = episode.pa, episode.pb, episode.assertions
        api = episode.api
        msgs = [{"role": "user", "content": task.prompt}]
        steps, finished, stop = 0, False, "max_steps"
        usage = {"prompt": 0, "completion": 0}
        step_budget = max_steps if max_steps is not None else episode.max_steps
        last_request = 0.0
        while steps < step_budget:
            try:
                if request_interval_seconds > 0 and last_request:
                    time.sleep(max(0.0, request_interval_seconds - (time.time() - last_request)))
                kwargs = {"model": model, "messages": msgs,
                          "tools": episode.tools, "tool_choice": "auto"}
                if max_completion_tokens is not None:
                    kwargs["max_tokens"] = max_completion_tokens
                last_request = time.time()
                r = client.chat.completions.create(**kwargs)
            except Exception as e:                       # noqa: BLE001
                label = "provider_timeout" if isinstance(e, TimeoutError) or "timeout" in str(e).lower() else "api_error"
                stop = f"{label}: {type(e).__name__}: {str(e)[:200]}"
                break
            if r.usage:
                usage["prompt"] += r.usage.prompt_tokens or 0
                usage["completion"] += r.usage.completion_tokens or 0
            if not r.choices:
                stop = "no_choices"
                break
            m = r.choices[0].message
            calls = m.tool_calls or []
            msgs.append({"role": "assistant", "content": m.content or "",
                         "tool_calls": [
                             {"id": c.id, "type": "function",
                              "function": {"name": c.function.name,
                                           "arguments": c.function.arguments}}
                             for c in calls] or None})
            if not calls:
                stop = "no_tool_call"
                break
            for c in calls:
                steps += 1
                name = c.function.name
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError as e:
                    out = {"ok": False, "error": {"code": "bad_json",
                                                  "message": str(e)}}
                else:
                    if name == "finish":
                        finished, stop = True, "finish"
                        out = {"ok": True, "acknowledged": True}
                    elif not hasattr(api, name):
                        out = {"ok": False, "error": {
                            "code": "unknown_tool", "message": f"no tool {name!r}"}}
                    else:
                        try:
                            out = getattr(api, name)(**args)
                        except TypeError as e:
                            out = {"ok": False, "error": {
                                "code": "bad_arguments", "message": str(e)[:300]}}
                        except Exception as e:           # noqa: BLE001
                            out = {"ok": False, "error": {
                                "code": "internal", "message": str(e)[:300]}}
                msgs.append({"role": "tool", "tool_call_id": c.id,
                             "content": json.dumps(out, default=str)[:4000]})
            if finished:
                break
        if domain.name == "teaching":
            from envs.teaching.scoring import score_session
            teaching = score_session(api)
            res = None
        else:
            teaching = None
            res = verifier.verify(pa, pb, assertions, with_details=True,
                                  domain=domain.name,
                                  artifacts_dir=art,
                                  step=episode.step_id)
        writes = [t for t in api.trace if t["action"] not in domain.read_only]
        files = list(getattr(api, "produced_files", []) or [])
        api.close()
        if stop == "finish":
            run_status = "completed"
        elif stop.startswith("api_error:"):
            run_status = "provider_error"
        elif stop.startswith("harness_error:"):
            run_status = "harness_error"
        else:
            run_status = "model_stopped"
        if teaching is not None:
            # Keep the baseline JSON shape stable while using the visual
            # benchmark's scope/accuracy/format score as the dense reward.
            failed = []
            if teaching.get("out_of_scope"):
                failed.append("TA-N1-out-of-scope")
            if teaching.get("criteria_passed") != teaching.get("criteria_total"):
                failed.append("TA-P1-assigned-coverage")
            if not teaching.get("gradesheet_exported"):
                failed.append("TA-F1-gradesheet")
            result_fields = {
                "criterion_pass_rate": teaching["score_100"] / 100.0,
                "task_passed": teaching["task_passed"],
                "criteria_passed": teaching["criteria_passed"],
                "criteria_total": teaching["criteria_total"],
                "failed": failed, "critical_failed": failed[:],
                "passed": [] if failed else ["TA-P1"],
                "by_kind": {"positive": [teaching["criteria_passed"], teaching["criteria_total"]]},
                "by_step": {}, "by_level": {}, "errors": {},
            }
        else:
            result_fields = res.as_dict()
        row = {"model": model, "rollout": idx, "ok": True, "stop": stop,
               "run_status": run_status,
               "eligible_for_aggregate": run_status in {
                   "completed", "model_stopped"},
               "steps": steps, "writes": len(writes),
               "failed_writes": sum(1 for w in writes if not w["ok"]),
               "seconds": round(time.time() - t0, 1), "usage": usage,
               "trace": api.trace, "files": files,
               "run_id": run_id if keep else None,
               "workdir": str(work) if keep else None,
               **result_fields}
        if keep:
            (work / "result.json").write_text(
                json.dumps(row, indent=2, default=str))
        return row
    except Exception as e:                               # noqa: BLE001
        return {"model": model, "rollout": idx, "ok": False,
                "stop": f"harness_error: {type(e).__name__}: {e}",
                "criterion_pass_rate": 0.0, "task_passed": False,
                "criteria_passed": 0, "criteria_total": 0,
                "run_status": "harness_error",
                "eligible_for_aggregate": False,
                "raw": 0.0, "final": 0.0, "passed": [], "failed": [],
                "critical_failed": [], "by_kind": {}, "by_step": {},
                "by_level": {}, "errors": {},
                "seconds": round(time.time() - t0, 1)}
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("-k", "--rollouts", type=int, default=3)
    ap.add_argument("--task", default="CB-SEED-001")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--max-steps", type=int, default=None,
                    help="Override the task step budget for bounded provider probes.")
    ap.add_argument("--max-completion-tokens", type=int, default=None,
                    help="Bound each model response for short diagnostic runs.")
    ap.add_argument("--timeout-seconds", type=float, default=90.0,
                    help="Per-provider request timeout; keep bounded for diagnostics.")
    ap.add_argument("--retries", type=int, default=1,
                    help="Provider retry count (retries can multiply a slow rollout).")
    ap.add_argument("--request-interval-seconds", type=float, default=0.0,
                    help="Minimum spacing between provider requests (useful for free pools).")
    ap.add_argument("--keep", action="store_true", default=True,
                    help="Keep workdirs + xlsx/docx under eval/results/runs/")
    ap.add_argument("--no-keep", action="store_true")
    a = ap.parse_args()
    keep = not a.no_keep

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key,
                    timeout=a.timeout_seconds, max_retries=a.retries)
    domain = resolve(a.task)
    task = domain.tasks[a.task]

    jobs = [(m, i) for m in a.models for i in range(a.rollouts)]
    rows = []
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        futs = {ex.submit(rollout, client, m, task, domain, i, keep=keep,
                          max_steps=a.max_steps,
                          max_completion_tokens=a.max_completion_tokens,
                          request_interval_seconds=a.request_interval_seconds): (m, i)
                for m, i in jobs}
        for f in as_completed(futs):
            r = f.result()
            rows.append(r)
            rate = r.get("criterion_pass_rate")
            if rate is None:
                rate = 0.0
            passed = r.get("task_passed") is True
            print(f"  {r['model']:34} #{r['rollout']}  "
                  f"rate={rate:.3f}  passed={passed}  "
                  f"stop={str(r['stop'])[:38]}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = OUT / f"baseline-{stamp}.json"
    payload = {"task": task.task_id, "domain": domain.name,
               "level": getattr(task, "level", 0),
               "rollouts": a.rollouts,
               "scoring": {
                   "metric": "criterion_pass_rate",
                   "pass": "task_passed (all criteria)",
               },
               "rows": rows}
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    (OUT / "latest.json").write_text(json.dumps({
        "baseline": str(out_path),
        "runs": [r.get("run_id") for r in rows if r.get("run_id")],
    }, indent=2))

    print(f"\n{'model':34} {'rate':>13} {'task-pass%':>10} {'pos':>7} {'prop':>7} "
          f"{'trail':>7} {'neg':>7} {'wr':>4} {'stp':>4}")
    print("-" * 104)
    for m in a.models:
        rs = [r for r in rows if r["model"] == m]
        if not rs:
            continue
        eligible = [r for r in rs if r.get("eligible_for_aggregate")]
        rates = [r.get("criterion_pass_rate", 0.0) for r in eligible]
        if not rates:
            print(f"{m:34} no eligible runs (provider/harness failures only)")
            continue
        sd = statistics.stdev(rates) if len(rates) > 1 else 0.0
        pass_frac = statistics.mean(
            1.0 if r.get("task_passed") is True else 0.0 for r in eligible)
        kinds = []
        for k in ("positive", "propagation", "trail", "negative"):
            vals = [r["by_kind"].get(k, [0, 1])[0] /
                    max(r["by_kind"].get(k, [0, 1])[1], 1)
                    for r in eligible if r.get("by_kind")]
            kinds.append(f"{statistics.mean(vals):>6.0%}" if vals else "     -")
        print(f"{m:34} {statistics.mean(rates):>6.1%} ±{sd:>5.1%} "
              f"{pass_frac:>6.1%} "
              + " ".join(f"{k:>7}" for k in kinds)
              + f" {statistics.mean(r.get('writes', 0) for r in eligible):>4.0f}"
              + f" {statistics.mean(r.get('steps', 0) for r in eligible):>4.0f}")
    print(f"\nwrote {out_path}")
    if keep:
        print(f"runs kept under {RUNS}")


if __name__ == "__main__":
    main()
