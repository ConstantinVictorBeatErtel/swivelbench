"""Localhost SwivelBench run visualizer.

  python3 -m viz.server
  open http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
RUNS = RESULTS / "runs"
MAPS = Path(__file__).parent / "maps"
STATIC = Path(__file__).parent / "static"


def _list_runs() -> list[dict]:
    out = []
    if not RUNS.exists():
        return out
    for d in sorted(RUNS.iterdir(), reverse=True):
        rj = d / "result.json"
        if not rj.exists():
            continue
        try:
            data = json.loads(rj.read_text())
        except json.JSONDecodeError:
            continue
        out.append({
            "run_id": d.name,
            "task": data.get("task") or d.name.split("_")[0],
            "domain": data.get("domain"),
            "model": data.get("model"),
            "final": data.get("final"),
            "raw": data.get("raw"),
            "stop": data.get("stop"),
            "files": len(data.get("files") or []),
        })
    return out


def _load_run(run_id: str) -> dict:
    path = RUNS / run_id / "result.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    data = json.loads(path.read_text())
    domain = data.get("domain")
    if not domain:
        tid = data.get("task") or ""
        domain = ("commercial_banking" if tid.startswith("CB")
                  else "grading" if tid.startswith("GR") else "unknown")
        data["domain"] = domain
    map_path = MAPS / f"{domain}.json"
    step_map = json.loads(map_path.read_text()) if map_path.exists() else {"steps": []}
    details = {d["id"]: d for d in (data.get("details") or [])}
    passed = set(data.get("passed") or [])
    failed = set(data.get("failed") or [])
    crit = set(data.get("critical_failed") or [])
    # Prefer original outcomes when materializing
    if data.get("original_passed") is not None:
        passed = set(data["original_passed"] or [])
        failed = set(data.get("original_failed") or [])
        crit = set(data.get("original_critical_failed") or [])
        data["final"] = data.get("original_final", data.get("final"))
        data["raw"] = data.get("original_raw", data.get("raw"))
        data["by_kind"] = data.get("original_by_kind", data.get("by_kind"))
        # Rebuild details pass flags
        for d in data.get("details") or []:
            d["passed"] = d["id"] in passed
            d["critical_failed"] = d["id"] in crit

    trace = data.get("original_trace") or data.get("trace") or []
    files = data.get("files") or []

    steps_out = []
    for step in step_map.get("steps") or []:
        acts = set(step.get("actions") or [])
        step_trace = [t for t in trace if t.get("action") in acts]
        assert_ids = step.get("asserts") or []
        grades = []
        for aid in assert_ids:
            det = details.get(aid, {"id": aid})
            ok = aid in passed
            grades.append({
                "id": aid,
                "kind": det.get("kind", "?"),
                "critical": bool(det.get("critical") or aid in crit),
                "passed": ok,
                "weight": det.get("weight", 1),
                "sql": det.get("sql", ""),
                "how": _how_line(det.get("sql") or "", aid, det.get("kind")),
            })
        # Attach files relevant to this step
        step_files = []
        for f in files:
            kind = f.get("kind")
            if step["id"] == "model" and kind == "xlsx":
                step_files.append(f)
            elif step["id"] in ("report", "grade") and kind == "docx":
                step_files.append(f)
        n_pass = sum(1 for g in grades if g["passed"])
        steps_out.append({
            **step,
            "trace": step_trace,
            "grades": grades,
            "files": step_files,
            "score": {"passed": n_pass, "total": len(grades)},
        })

    return {
        "run": {
            "run_id": run_id,
            "task": data.get("task"),
            "domain": domain,
            "model": data.get("model"),
            "final": data.get("final"),
            "raw": data.get("raw"),
            "stop": data.get("stop"),
            "steps_count": data.get("steps"),
            "writes": data.get("writes"),
            "by_kind": data.get("by_kind"),
            "critical_failed": list(crit),
            "kind_share": data.get("kind_share") or {
                "positive": 0.2, "propagation": 0.3, "negative": 0.35, "trail": 0.15},
            "systems": step_map.get("systems", []),
        },
        "graph": steps_out,
        "files": files,
        "trace": trace,
    }


def _how_line(sql: str, aid: str, kind: str | None) -> str:
    s = " ".join((sql or "").split())
    if len(s) > 160:
        s = s[:157] + "..."
    return s or f"{kind or 'assert'} {aid}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[viz] {args[0] if args else fmt}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(code, json.dumps(obj, default=str).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        if path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if path == "/api/runs":
            return self._json(200, {"runs": _list_runs()})
        if path.startswith("/api/run/"):
            run_id = path[len("/api/run/"):].strip("/")
            try:
                return self._json(200, _load_run(run_id))
            except FileNotFoundError:
                return self._json(404, {"error": "run not found"})
        if path.startswith("/files/"):
            # /files/<run_id>/artifacts/...
            rel = path[len("/files/"):]
            parts = rel.split("/", 1)
            if len(parts) != 2:
                return self._json(400, {"error": "bad path"})
            run_id, rest = parts
            fp = (RUNS / run_id / rest).resolve()
            if not str(fp).startswith(str((RUNS / run_id).resolve())):
                return self._json(403, {"error": "forbidden"})
            if not fp.is_file():
                return self._json(404, {"error": "missing file"})
            ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            return self._send(200, fp.read_bytes(), ctype)
        if path.startswith("/static/"):
            fp = STATIC / path[len("/static/"):]
            if fp.is_file():
                ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
                return self._send(200, fp.read_bytes(), ctype)
        self._json(404, {"error": "not found"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"SwivelBench viz → http://{a.host}:{a.port}")
    print(f"runs dir: {RUNS}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
