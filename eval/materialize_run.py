"""Materialize a past baseline row into a kept run with real xlsx/docx files.

Replays the model's tool trace through the ActionAPI (no LLM), then verifies
with assertion details for the viz.

  python3 -m eval.materialize_run eval/results/baseline-20260808-135321.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.registry import resolve  # noqa: E402

OUT = Path(__file__).parent / "results" / "runs"


def materialize(baseline_path: Path, *, row_index: int = 0) -> Path:
    data = json.loads(baseline_path.read_text())
    row = data["rows"][row_index]
    task_id = data["task"]
    domain = resolve(task_id)
    task = domain.tasks[task_id]
    model = row.get("model", "unknown").replace("/", "_").replace(":", "_")
    run_id = f"{task_id}_{model}_materialized_{time.strftime('%Y%m%d-%H%M%S')}"
    work = OUT / run_id
    work.mkdir(parents=True, exist_ok=True)
    art = work / "artifacts"
    pa, pb, assertions = domain.prepare(task, work)
    api = domain.make_api(pa, pb, task, artifacts_dir=art)

    skip = {"finish"}
    for t in row.get("trace") or []:
        name = t.get("action")
        if not name or name in skip or not t.get("ok", True):
            continue
        if not hasattr(api, name):
            continue
        args = t.get("args") or {}
        try:
            getattr(api, name)(**args)
        except TypeError:
            # Older traces may omit optional args
            with suppress(Exception):
                getattr(api, name)(**{k: v for k, v in args.items() if v is not None})
        except Exception:  # noqa: BLE001
            pass

    res = verifier.verify(pa, pb, assertions, with_details=True,
                          domain=domain.name, artifacts_dir=art)
    out = {
        **{k: row.get(k) for k in (
            "model", "rollout", "stop", "steps", "writes", "usage", "seconds")},
        "task": task_id,
        "domain": domain.name,
        "run_id": run_id,
        "workdir": str(work),
        "trace": api.trace,
        "files": list(api.produced_files),
        "source_baseline": str(baseline_path),
        "source_kind": "replay",
        "run_status": "completed",
        "eligible_for_aggregate": True,
        **res.as_dict(),
        "original_criterion_pass_rate": row.get("criterion_pass_rate"),
        "original_task_passed": row.get("task_passed"),
        "original_final": row.get("final"),
        "original_raw": row.get("raw"),
        "original_failed": row.get("failed"),
        "original_critical_failed": row.get("critical_failed"),
        "original_by_kind": row.get("by_kind"),
        "original_passed": row.get("passed"),
        "original_trace": row.get("trace"),
    }
    api.close()
    (work / "result.json").write_text(json.dumps(out, indent=2, default=str))
    (Path(__file__).parent / "results" / "latest.json").write_text(json.dumps({
        "baseline": str(baseline_path),
        "runs": [run_id],
        "primary": run_id,
    }, indent=2))
    return work


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("--row", type=int, default=0)
    a = ap.parse_args()
    work = materialize(Path(a.baseline), row_index=a.row)
    print(f"materialized {work}")
    files = list((work / "artifacts").rglob("*"))
    for f in files:
        if f.is_file():
            print(f"  {f.relative_to(work)}")


if __name__ == "__main__":
    main()
