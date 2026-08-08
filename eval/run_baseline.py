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
from envs.registry import resolve  # noqa: E402

OUT = Path(__file__).parent / "results"
RUNS = OUT / "runs"


def rollout(client: OpenAI, model: str, task, domain, idx: int,
            *, keep: bool) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_model = model.replace("/", "_").replace(":", "_")
    run_id = f"{task.task_id}_{safe_model}_r{idx}_{stamp}"
    work = RUNS / run_id if keep else Path(tempfile.mkdtemp(prefix=f"sb_{idx}_"))
    if keep:
        work.mkdir(parents=True, exist_ok=True)
    art = work / "artifacts"
    t0 = time.time()
    try:
        pa, pb, assertions = domain.prepare(task, work)
        api = domain.make_api(pa, pb, task, artifacts_dir=art)
        msgs = [{"role": "user", "content": task.prompt}]
        steps, finished, stop = 0, False, "max_steps"
        usage = {"prompt": 0, "completion": 0}
        while steps < task.max_steps:
            try:
                r = client.chat.completions.create(
                    model=model, messages=msgs, tools=domain.tools,
                    tool_choice="auto")
            except Exception as e:                       # noqa: BLE001
                stop = f"api_error: {type(e).__name__}: {str(e)[:200]}"
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
        res = verifier.verify(pa, pb, assertions, with_details=True,
                              domain=domain.name,
                              artifacts_dir=art)
        writes = [t for t in api.trace if t["action"] not in domain.read_only]
        files = list(getattr(api, "produced_files", []) or [])
        api.close()
        row = {"model": model, "rollout": idx, "ok": True, "stop": stop,
               "steps": steps, "writes": len(writes),
               "failed_writes": sum(1 for w in writes if not w["ok"]),
               "seconds": round(time.time() - t0, 1), "usage": usage,
               "trace": api.trace, "files": files,
               "run_id": run_id if keep else None,
               "workdir": str(work) if keep else None,
               **res.as_dict()}
        if keep:
            (work / "result.json").write_text(
                json.dumps(row, indent=2, default=str))
        return row
    except Exception as e:                               # noqa: BLE001
        return {"model": model, "rollout": idx, "ok": False,
                "stop": f"harness_error: {type(e).__name__}: {e}",
                "criterion_pass_rate": 0.0, "task_passed": False,
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
    ap.add_argument("--keep", action="store_true", default=True,
                    help="Keep workdirs + xlsx/docx under eval/results/runs/")
    ap.add_argument("--no-keep", action="store_true")
    a = ap.parse_args()
    keep = not a.no_keep

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key,
                    timeout=300.0, max_retries=3)
    domain = resolve(a.task)
    task = domain.tasks[a.task]

    jobs = [(m, i) for m in a.models for i in range(a.rollouts)]
    rows = []
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        futs = {ex.submit(rollout, client, m, task, domain, i, keep=keep): (m, i)
                for m, i in jobs}
        for f in as_completed(futs):
            r = f.result()
            rows.append(r)
            rate = r.get("criterion_pass_rate", r.get("final", 0.0))
            passed = r.get("task_passed", rate >= 1.0)
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

    print(f"\n{'model':34} {'rate':>13} {'pass%':>7} {'pos':>7} {'prop':>7} "
          f"{'trail':>7} {'neg':>7} {'wr':>4} {'stp':>4}")
    print("-" * 104)
    for m in a.models:
        rs = [r for r in rows if r["model"] == m]
        if not rs:
            continue
        rates = [r.get("criterion_pass_rate", r.get("final", 0.0)) for r in rs]
        sd = statistics.stdev(rates) if len(rates) > 1 else 0.0
        pass_frac = statistics.mean(
            1.0 if r.get("task_passed") else 0.0 for r in rs)
        kinds = []
        for k in ("positive", "propagation", "trail", "negative"):
            vals = [r["by_kind"].get(k, [0, 1])[0] /
                    max(r["by_kind"].get(k, [0, 1])[1], 1)
                    for r in rs if r.get("by_kind")]
            kinds.append(f"{statistics.mean(vals):>6.0%}" if vals else "     -")
        print(f"{m:34} {statistics.mean(rates):>6.1%} ±{sd:>5.1%} "
              f"{pass_frac:>6.1%} "
              + " ".join(f"{k:>7}" for k in kinds)
              + f" {statistics.mean(r.get('writes', 0) for r in rs):>4.0f}"
              + f" {statistics.mean(r.get('steps', 0) for r in rs):>4.0f}")
    print(f"\nwrote {out_path}")
    if keep:
        print(f"runs kept under {RUNS}")


if __name__ == "__main__":
    main()
