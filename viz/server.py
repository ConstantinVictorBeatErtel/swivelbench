"""Localhost SwivelBench environment design + run explorer.

  python3 -m viz.server
  open http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
RUNS = RESULTS / "runs"
MAPS = Path(__file__).parent / "maps"
STATIC = Path(__file__).parent / "static"
SAMPLES = Path(__file__).parent / "samples"
# Primary UI: Swivelbench Environment Design (baseline run explorers)
APP = ROOT / "Swivelbench Environment Design"
HOME_PAGE = "Commercial Banking.dc.html"
ALIASES = {
    "/": HOME_PAGE,
    "/index.html": HOME_PAGE,
    "/commercial-banking": HOME_PAGE,
    "/commercial-banking.html": HOME_PAGE,
    "/grading": "Grading.dc.html",
    "/grading.html": "Grading.dc.html",
}

DEFAULT_KIND_WORDS = {
    "positive": "Required",
    "negative": "Forbidden",
    "propagation": "Consistency",
    "trail": "Audit trail",
    "format": "File format",
}


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
        domain = (
            "commercial_banking" if tid.startswith("CB")
            else "grading" if tid.startswith("GR")
            else "unknown"
        )
        data["domain"] = domain
    map_path = MAPS / f"{domain}.json"
    step_map = json.loads(map_path.read_text()) if map_path.exists() else {"steps": []}
    checks = step_map.get("checks") or {}
    kind_words = {**DEFAULT_KIND_WORDS, **(step_map.get("kind_words") or {})}

    details = {d["id"]: d for d in (data.get("details") or [])}
    passed = set(data.get("passed") or [])
    failed = set(data.get("failed") or [])
    crit = set(data.get("critical_failed") or [])
    if data.get("original_passed") is not None:
        passed = set(data["original_passed"] or [])
        failed = set(data.get("original_failed") or [])
        crit = set(data.get("original_critical_failed") or [])
        data["final"] = data.get("original_final", data.get("final"))
        data["raw"] = data.get("original_raw", data.get("raw"))
        data["by_kind"] = data.get("original_by_kind", data.get("by_kind"))
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
            kind = det.get("kind") or "?"
            copy = checks.get(aid) or {}
            title = copy.get("title") or f"Check {aid}"
            why = copy.get("why") or "No plain-language description yet."
            critical = bool(det.get("critical") or aid in crit)
            ok = aid in passed
            grades.append({
                "id": aid,
                "kind": kind,
                "kind_label": kind_words.get(kind, kind),
                "critical": critical,
                "passed": ok,
                "weight": det.get("weight", 1),
                "title": title,
                "why": why,
                "verdict": (
                    "Passed" if ok
                    else ("Critical miss" if critical else "Missed")
                ),
            })
        step_files = []
        for f in files:
            kind = f.get("kind")
            if step["id"] == "model" and kind == "xlsx":
                step_files.append(f)
            elif step["id"] in ("report", "grade") and kind == "docx":
                step_files.append(f)
        n_pass = sum(1 for g in grades if g["passed"])
        n_crit_fail = sum(1 for g in grades if g["critical"] and not g["passed"])
        steps_out.append({
            **{k: v for k, v in step.items() if k != "asserts"},
            "trace": step_trace,
            "grades": grades,
            "files": step_files,
            "score": {
                "passed": n_pass,
                "total": len(grades),
                "critical_misses": n_crit_fail,
            },
        })

    by_kind = data.get("by_kind") or {}
    kind_summary = []
    for k in ("positive", "propagation", "negative", "trail", "format"):
        if k not in by_kind:
            continue
        v = by_kind[k]
        kind_summary.append({
            "kind": k,
            "label": kind_words.get(k, k),
            "score": v,
        })

    crit_titles = []
    for aid in sorted(crit):
        copy = checks.get(aid) or {}
        crit_titles.append(copy.get("title") or aid)

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
            "by_kind": by_kind,
            "kind_summary": kind_summary,
            "critical_failed": list(crit),
            "critical_titles": crit_titles,
            "kind_share": data.get("kind_share") or {
                "positive": 0.18, "propagation": 0.27,
                "negative": 0.32, "trail": 0.13, "format": 0.10,
            },
            "systems": step_map.get("systems", []),
            "story": _score_story(data.get("final"), crit_titles),
        },
        "graph": steps_out,
        "files": files,
        "trace": trace,
    }


def _score_story(final: float | None, crit_titles: list[str]) -> str:
    if final is None:
        return "No score yet."
    if crit_titles:
        names = "; ".join(crit_titles[:3])
        extra = f" (+{len(crit_titles) - 3} more)" if len(crit_titles) > 3 else ""
        return (
            f"Final capped at {final:.2f} because of critical misses: "
            f"{names}{extra}."
        )
    if final >= 0.999:
        return "Full credit — every check in this run passed."
    return f"Final score {final:.2f}. No critical misses; some soft checks failed."


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
        self._send(
            code,
            json.dumps(obj, default=str).encode(),
            "application/json; charset=utf-8",
        )

    def _safe_file(self, root: Path, rel: str) -> Path | None:
        if not rel or rel.endswith("/"):
            return None
        fp = (root / rel).resolve()
        try:
            fp.relative_to(root.resolve())
        except ValueError:
            return None
        return fp if fp.is_file() else None

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)

        if path == "/api/runs":
            return self._json(200, {"runs": _list_runs()})
        if path.startswith("/api/run/"):
            run_id = path[len("/api/run/"):].strip("/")
            try:
                return self._json(200, _load_run(run_id))
            except FileNotFoundError:
                return self._json(404, {"error": "run not found"})
        if path.startswith("/files/"):
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

        # Live run explorer (previous UI)
        if path in ("/runs", "/runs.html", "/legacy"):
            fp = STATIC / "index.html"
            return self._send(200, fp.read_bytes(), "text/html; charset=utf-8")
        if path.startswith("/static/"):
            fp = self._safe_file(STATIC, path[len("/static/"):])
            if fp:
                ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
                return self._send(200, fp.read_bytes(), ctype)

        if path.startswith("/samples/"):
            fp = self._safe_file(SAMPLES, path[len("/samples/"):])
            if fp:
                ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
                # Force download for Office files in the design UI.
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(fp.stat().st_size))
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{fp.name}"',
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(fp.read_bytes())
                return

        # Primary app: Environment Design
        rel = ALIASES.get(path, path.lstrip("/"))
        fp = self._safe_file(APP, rel)
        if fp:
            ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            if fp.suffix.lower() in {".html", ".htm"}:
                ctype = "text/html; charset=utf-8"
            elif fp.suffix.lower() == ".js":
                ctype = "application/javascript; charset=utf-8"
            elif fp.suffix.lower() == ".css":
                ctype = "text/css; charset=utf-8"
            return self._send(200, fp.read_bytes(), ctype)

        self._json(404, {"error": "not found"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"SwivelBench → http://{a.host}:{a.port}")
    print(f"app: {APP}")
    print(f"runs explorer: http://{a.host}:{a.port}/runs")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
