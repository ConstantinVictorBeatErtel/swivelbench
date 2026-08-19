#!/usr/bin/env python3
"""Read-only capability probe for the Ed (edstem.org) API.

Purpose: find out what an Ed API token can *see*, so you can decide whether to
ask a course instructor for a proper data export. This is a scope check, not a
collection tool. It reads at most one page of one course's threads, prints the
shape of a single thread object, and writes nothing to disk.

ENDPOINT PROVENANCE — READ THIS
-------------------------------
Ed does not publish HTTP endpoint documentation. Ed *does* officially issue API
tokens (https://edstem.org/us/settings/api-tokens), so token use is a supported
product feature, but the specific paths below are NOT documented by Ed. Every
public reference to them traces back to third parties inspecting the Ed web
app's own network calls, and those authors state the API is in beta and may
change without notice.

The paths are therefore marked UNVERIFIED and kept in one block so you can
replace them if Ed support gives you authoritative ones. If a path 404s, that
most likely means the path is stale -- not that your token lacks access. The
summary table reports 404 separately from 401/403 for exactly this reason.

Safety properties (enforced, not merely intended):
  * GET only. `_get` is the sole network path and hardcodes requests.get.
  * One request at a time, 1s delay between calls. No threads, no retries.
  * First page only, smallest page size. No pagination, no crawling.
  * No response body is ever written to disk. stdout only.
  * Long strings are truncated to 40 chars when printing thread shape.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

# --- UNVERIFIED endpoint paths (see module docstring) -----------------------
# Relative to the base URL. Replace if you obtain authoritative paths from Ed.
IDENTITY_PATH = "/user"
THREADS_PATH = "/courses/{course_id}/threads"
# Smallest page size the API is understood to accept. We want shape, not data.
THREADS_PARAMS = {"limit": 1, "offset": 0}
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://edstem.org/api"
REQUEST_DELAY_SEC = 1.0
TRUNCATE_AT = 40
TIMEOUT_SEC = 30

# Populated by _get; rendered by print_summary.
CALL_LOG: list[dict] = []


def _get(session: requests.Session, base_url: str, path: str, params: dict | None = None) -> requests.Response | None:
    """The only network call in this program. GET only, one at a time.

    Sleeps REQUEST_DELAY_SEC *before* each call so successive calls are always
    spaced, regardless of how fast the previous one returned. Never retries.
    """
    url = f"{base_url.rstrip('/')}{path}"
    time.sleep(REQUEST_DELAY_SEC)
    try:
        # requests.get is hardcoded: this program has no way to issue a
        # POST/PUT/PATCH/DELETE, by construction.
        resp = session.get(url, params=params, timeout=TIMEOUT_SEC)
    except requests.RequestException as exc:
        CALL_LOG.append({"url": url, "status": "ERR", "note": type(exc).__name__})
        print(f"  ! request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    CALL_LOG.append({"url": url, "status": resp.status_code, "note": ""})
    return resp


def _truncate(value: str) -> str:
    flat = " ".join(value.split())
    if len(flat) <= TRUNCATE_AT:
        return flat
    return flat[:TRUNCATE_AT] + "..."


def _describe(value, depth: int = 0) -> str:
    """Return a type description, never the full content."""
    if isinstance(value, str):
        return f"str(len={len(value)}) ~ {_truncate(value)!r}"
    if isinstance(value, bool):
        return f"bool = {value}"
    if isinstance(value, (int, float)):
        return f"{type(value).__name__} = {value}"
    if value is None:
        return "null"
    if isinstance(value, list):
        if not value:
            return "list(empty)"
        return f"list(len={len(value)}) of {type(value[0]).__name__}"
    if isinstance(value, dict):
        if depth >= 1:
            return f"dict({len(value)} keys: {', '.join(sorted(value)[:6])}…)"
        return f"dict({len(value)} keys)"
    return type(value).__name__


def print_identity(payload: dict) -> list[dict]:
    """Print who the token belongs to and which courses it can see."""
    user = payload.get("user") or {}
    ident = {k: user.get(k) for k in ("id", "name", "email", "role") if k in user}
    print("\n[identity]")
    if ident:
        for key, val in ident.items():
            print(f"  {key}: {val}")
    else:
        print(f"  (unexpected shape; top-level keys: {', '.join(sorted(payload)[:12])})")

    # Ed nests role-per-course alongside the course object.
    entries = payload.get("courses") or []
    print(f"\n[courses visible to this token]  count={len(entries)}")
    if not entries:
        print("  (none)")
        return []

    rows = []
    for entry in entries:
        course = entry.get("course", entry) if isinstance(entry, dict) else {}
        rows.append({
            "id": course.get("id"),
            "code": course.get("code") or course.get("name"),
            "role": (entry.get("role") if isinstance(entry, dict) else None) or "?",
            "year": course.get("year") or "",
        })

    width = max((len(str(r["code"])) for r in rows if r["code"]), default=20)
    width = min(max(width, 10), 44)
    print(f"  {'ID':<8}  {'CODE':<{width}}  {'ROLE':<12}  YEAR")
    for r in sorted(rows, key=lambda r: str(r["id"])):
        code = str(r["code"])[:width]
        print(f"  {str(r['id']):<8}  {code:<{width}}  {str(r['role']):<12}  {r['year']}")
    return rows


def print_thread_shape(payload: dict) -> bool:
    """Print field names and types for ONE thread. Content stays truncated."""
    threads = payload.get("threads")
    if threads is None:
        for key in ("items", "data", "results"):
            if isinstance(payload.get(key), list):
                threads = payload[key]
                break
    if not isinstance(threads, list):
        print("\n[thread schema]")
        print(f"  Could not locate a thread list. Top-level keys: {', '.join(sorted(payload)[:12])}")
        return False
    if not threads:
        print("\n[thread schema]")
        print("  Endpoint returned 200 with zero threads (empty course, or filtered out).")
        return True

    thread = threads[0]
    print(f"\n[thread schema]  (1 of {len(threads)} returned; field names + types only)")
    for key in sorted(thread):
        print(f"  {key:<24} {_describe(thread[key])}")
    return True


def print_summary(scope_notes: list[str]) -> None:
    print("\n" + "=" * 74)
    print("SUMMARY — endpoint results")
    print("=" * 74)
    print(f"  {'STATUS':<8}  {'CLASS':<14}  ENDPOINT")
    for call in CALL_LOG:
        status = call["status"]
        if status == "ERR":
            klass = "network-error"
        elif status == 200:
            klass = "ok"
        elif status in (401, 403):
            klass = "denied"
        elif status == 404:
            klass = "not-found"
        else:
            klass = "other"
        note = f"  ({call['note']})" if call["note"] else ""
        print(f"  {str(status):<8}  {klass:<14}  {call['url']}{note}")

    print("\n" + "=" * 74)
    print("EFFECTIVE READ SCOPE")
    print("=" * 74)
    for note in scope_notes:
        print(f"  - {note}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only scope check for an Ed API token. Reads one page of one course."
    )
    parser.add_argument("course_id", help="A single course ID to test thread read access against.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ED_BASE_URL", DEFAULT_BASE_URL),
        help=(
            "API base URL (default: %(default)s). Ed runs regional hosts; if every "
            "call 404s, try https://us.edstem.org/api"
        ),
    )
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("ED_API_TOKEN", "").strip()
    if not token:
        print("ED_API_TOKEN is not set. Copy .env.example to .env and paste your token.", file=sys.stderr)
        print("Create a token at https://edstem.org/us/settings/api-tokens", file=sys.stderr)
        return 2

    print("Ed API read-only scope probe")
    print(f"  base URL : {args.base_url}")
    print(f"  token    : ...{token[-4:]} (len={len(token)})")
    print(f"  pacing   : 1 request at a time, {REQUEST_DELAY_SEC}s apart, no retries")
    print("  NOTE     : endpoint paths are UNVERIFIED (Ed publishes no HTTP API docs).")
    print("             A 404 means the path is likely stale, NOT that access is denied.")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ed-scope-probe/1.0 (read-only capability check)",
    })

    scope_notes: list[str] = []

    # --- 1) identity -------------------------------------------------------
    print("\n> GET identity endpoint ...")
    resp = _get(session, args.base_url, IDENTITY_PATH)
    courses: list[dict] = []
    if resp is None:
        scope_notes.append("Identity call failed at the network layer; nothing could be determined.")
        print_summary(scope_notes)
        return 1

    if resp.status_code == 200:
        try:
            payload = resp.json()
        except ValueError:
            print("  ! 200 but body was not JSON (likely an HTML login page -- token may be unusable here).")
            scope_notes.append("Identity returned 200 but non-JSON; treat the token as unconfirmed.")
            print_summary(scope_notes)
            return 1
        courses = print_identity(payload)
        scope_notes.append(f"Token authenticates successfully and sees {len(courses)} course(s).")
    elif resp.status_code in (401, 403):
        print(f"  ! {resp.status_code} — token rejected. Body: {_truncate(resp.text)}")
        scope_notes.append(f"Token rejected at identity ({resp.status_code}); it may be expired or revoked.")
        print_summary(scope_notes)
        return 1
    else:
        print(f"  ! {resp.status_code}. Body: {_truncate(resp.text)}")
        scope_notes.append(f"Identity returned {resp.status_code}; endpoint path is likely stale.")
        print_summary(scope_notes)
        return 1

    # --- 2) threads for exactly ONE course --------------------------------
    course_id = args.course_id
    known = {str(r["id"]) for r in courses}
    if known and str(course_id) not in known:
        print(f"\n  ! Course {course_id} is not in the list above; requesting it anyway as you asked.")
        print("    Expect 403 if your account is not enrolled in it.")

    my_role = next((r["role"] for r in courses if str(r["id"]) == str(course_id)), "unknown")
    print(f"\n> GET threads for course {course_id} (role: {my_role}, limit=1, first page only) ...")
    resp = _get(session, args.base_url, THREADS_PATH.format(course_id=course_id), THREADS_PARAMS)

    if resp is None:
        scope_notes.append("Thread call failed at the network layer; thread scope undetermined.")
    elif resp.status_code == 200:
        try:
            payload = resp.json()
        except ValueError:
            print("  ! 200 but body was not JSON.")
            scope_notes.append("Thread endpoint returned 200 with a non-JSON body; scope unclear.")
        else:
            ok = print_thread_shape(payload)
            if ok:
                scope_notes.append(
                    f"READ ACCESS TO THREAD HISTORY: YES for course {course_id} (role: {my_role})."
                )
                scope_notes.append(
                    "Scope appears to follow your normal in-app permissions -- the token acts as you, "
                    "so it sees what you can see in the web UI, no more."
                )
    elif resp.status_code in (401, 403):
        print(f"  ! {resp.status_code} — denied. Body: {_truncate(resp.text)}")
        scope_notes.append(
            f"READ ACCESS TO THREAD HISTORY: NO for course {course_id} -- HTTP {resp.status_code} "
            f"({'unauthorized' if resp.status_code == 401 else 'forbidden'})."
        )
        scope_notes.append("Ask the course staff for an export rather than working around this.")
    elif resp.status_code == 404:
        print(f"  ! 404. Body: {_truncate(resp.text)}")
        scope_notes.append(
            f"Thread endpoint returned 404. Ambiguous: either course {course_id} does not exist, "
            "or the UNVERIFIED path is stale. Not evidence of a permission denial."
        )
    else:
        print(f"  ! {resp.status_code}. Body: {_truncate(resp.text)}")
        scope_notes.append(f"Thread endpoint returned {resp.status_code}; scope undetermined.")

    scope_notes.append("Probe made GET requests only; no data was written to disk.")
    print_summary(scope_notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
