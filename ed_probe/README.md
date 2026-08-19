# Ed API scope probe

A one-shot, read-only check of what an Ed (edstem.org) API token can see — so you
can decide whether to ask a course instructor for a proper export.

This is **not** an exporter, crawler, or scraper, and it is deliberately built so
it cannot become one without being rewritten.

## Setup

```bash
cd ed_probe
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then paste your token into .env
```

Create a token at <https://edstem.org/us/settings/api-tokens>. The token is a
bearer credential for your entire Ed account — `.env` is gitignored here and in
the repo root; keep it that way.

## Run

```bash
./.venv/bin/python probe_ed.py <COURSE_ID>
```

If every call returns 404, try Ed's regional host:

```bash
./.venv/bin/python probe_ed.py <COURSE_ID> --base-url https://us.edstem.org/api
```

## What it does

1. `GET` the identity endpoint, printing your account and every course the token
   can see, with course ID and your role in each.
2. `GET` one page of threads for the single course ID you pass, at the smallest
   page size (`limit=1`).
3. Print that thread's **shape only** — field names and types, with string
   content truncated to 40 characters.
4. Print a summary table of endpoint statuses and the effective read scope.

## Guarantees

| Constraint | How it's enforced |
|---|---|
| Read-only | `_get()` is the only network path; it hardcodes `requests.get`. No write verb appears anywhere in the file. |
| One at a time, 1s apart | `_get()` sleeps before every call. No threads, no async, no pool. |
| No retries | No retry logic; a failure is logged and reported. |
| First page only | `limit=1, offset=0`, and nothing reads a `next`/cursor field. |
| Nothing written to disk | No `open()`, no `json.dump`, no serialization. stdout only. |

## Caveat on endpoint paths

Ed publishes **no HTTP API documentation**. Ed does officially issue API tokens,
so token use is a supported feature, but the specific paths in this script are
undocumented — every public reference to them traces back to third parties
inspecting the Ed web app's own network traffic, and those authors note the API
is in beta and can change without notice.

The paths are marked `UNVERIFIED` in one block at the top of `probe_ed.py` so you
can swap in authoritative ones if Ed support provides them.

**This is why the summary table reports 404 separately from 401/403.** A 404 most
likely means the path is stale, *not* that your token was denied. Only 401/403 is
evidence about your permissions.
