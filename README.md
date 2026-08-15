# SwivelBench

Dual-system RL / eval environments for enterprise workflows. Agents act through
a typed tool API (no raw SQL). Scoring is **rubric RLVR**: deterministic SQL +
OOXML criteria over two ATTACHed SQLite systems. No LLM judge in the default
scorer (optional LLM criteria must pass an adversarial calibration loop first).

[View the interactive benchmark showcase →](https://constantinvictorbeatertel.github.io/swivelbench/)

| Domain | Systems | Tasks |
|---|---|---|
| Commercial banking | `credit_workbench` + `ncino_core` | `CB-*` (E2E) and `CB-*@S*` (steps) |
| Grading | `inbox` + `gradescope` | `GR-*` (E2E) and `GR-*@S*` (steps) |

Two tracks:

- **Track A (training):** one self-contained prompt per workflow step, gold
  snapshot state for prior work, no prior agent transcript.
- **Track B (eval):** thin end-to-end orchestrator prompt for composition /
  goal-directed execution.

## Quick start

Python 3.11+, stdlib only for core:

```bash
python3 eval/oracle.py --task CB-SEED-001
python3 eval/oracle.py --task CB-SEED-001@S3_model
python3 eval/oracle.py --task GR-SEED-001
python3 -m pytest tests/test_adversarial.py tests/test_steps.py -v
python3 -m eval.calibrate_criterion --demo
```

Oracle must achieve `task_passed` (criterion_pass_rate `1.000`). Wrong states
must not pass the task.

Published model grading is strict: a run is `task_passed` only when every
active rubric criterion passes. `criterion_pass_rate` and `score_100` are
diagnostic/training signals, not passing thresholds. Provider or harness
failures are invalid runs and are excluded from model aggregates.

### Model baselines (OpenRouter)

```bash
uv pip install openai pytest ruff
export OPENROUTER_API_KEY=sk-or-v1-...   # no wrapping quotes in the value
python3 -m eval.run_baseline \
  --models nvidia/nemotron-3-super-120b-a12b:free \
  --task CB-SEED-001 -k 1
```

### Localhost app

```bash
python3 -m viz.server --port 8765
```

## Scoring

Replaces the old `raw` / `final` / `KIND_SHARE` / `CRITICAL_CAP` scheme.

| Metric | Meaning |
|---|---|
| `criterion_pass_rate` | Fraction of active rubric criteria satisfied — **dense RL reward** |
| `score_100` | `criterion_pass_rate × 100` — **0–100 benchmark score** |
| `task_passed` | True iff **all** criteria pass — published pass/fail |
| `criteria_passed / criteria_total` | Exact published rubric count; the source of truth beside `task_passed` |

Passing a task requires every rubric criterion to be satisfied. Partial credit
still shows up in `score_100`.

Each criterion carries metadata:

- `step=` workflow step (`S1_template` … / `S1_rubric` …)
- `level=` Hierarchy of Agentic Capabilities: `tool` · `plan` · `adapt` · `ground` · `reason`
- `role=` `required` · `bonus` · `penalty`

Format checks (`F*`) unzip produced `.xlsx` / `.docx` files — see
`docs/format_judgement.md`. Optional LLM prose/groundedness criteria are **not**
in the default score until calibrated via `eval/calibrate_criterion.py`.

## Design principles & related work

Ideas adopted from recent papers (cited):

### Expert rubrics for RLVR — [Mehta et al., 2026](https://arxiv.org/abs/2606.09118)

| Idea | In SwivelBench |
|---|---|
| **Maximum Viable Atomicity** | Criteria target the smallest *meaningful* unit (not micro-splits that reward confident wrong answers). |
| **Intent over literalism** | Step prompts restate the job; graded checklists align to criteria IDs. |
| **LLM-judge calibration loop** | Draft → hand-grade → judge agree → adversarial flip-test (`eval/calibrate_criterion.py`). |
| **Dense gradient + hard pass** | `criterion_pass_rate` trains; `task_passed` requires all criteria. |
| **Required / bonus / penalty** | Trap avoidance is `role=penalty`; core checks are `required`. |
| **Same rubrics for eval and RL** | One assertion schema drives both metrics. |
| **Hierarchy of Agentic Capabilities** | Every criterion tagged `level=tool\|plan\|adapt\|ground\|reason`. |
| **GRPO + rubric fraction** | Verifiers adapter rewards `criterion_pass_rate` on step episodes. |

### FORCE-Bench (enterprise finance) — [Pauli et al., 2026](https://arxiv.org/abs/2607.19409)

| Idea | In SwivelBench |
|---|---|
| Multi-dimension quality | Accuracy / groundedness / structure via criterion families + format checks. |
| Task types, not one mega-query | Distinct step episodes; public-company catalog scaffolds multiple report types. |
| Expert-calibrated domain rubrics | Banking/TA policies explicit and tool-discoverable. |
| Shared operational conditions | Common tool API across agents (latency budgets optional later). |

### SARA (compute-efficient RLVR) — [Nomand et al., 2026](https://arxiv.org/abs/2607.26253)

| Idea | In SwivelBench |
|---|---|
| Saturated groups waste GRPO | Prefer short step episodes with mixed difficulty. |
| Verifiable rewards | Default scorer is SQL + OOXML RLVR. |
| Adaptive allocation (later) | Adapter logs `saturated_hint` when rate is 0 or 1. |

### Goal-directed execution / office→SWE — [Ritchie et al., 2026](https://arxiv.org/abs/2608.01604)

| Idea | In SwivelBench |
|---|---|
| Nested goal loops | Track A = one goal loop per step; Track B = long-horizon composition. |
| Dense reward = criterion fraction | Trajectory-level `criterion_pass_rate`, not per-tool shaping. |
| Keep long-horizon eval | E2E `CB-*` / `GR-*` remain the composition suite. |

## Public-company credit book (scaffold)

`envs/commercial_banking/fixtures/public_companies.json` holds placeholders for
multiple public companies with distinct `report_type`s and
`ground_truth_metrics` for real-number verification. Concrete tickers and report
types are **TBD** — see `envs/commercial_banking/public_companies.py`.

## Layout

```
core/                       db, verifier, steps, xlsx/docx writers
envs/commercial_banking/    E2E + step episodes, public-company scaffold
envs/grading/               E2E + step episodes
envs/registry.py            CB-/GR- dispatch (incl. task@step ids)
eval/                       oracle, baseline, materialize, calibrate_criterion
viz/                        localhost run explorer
adapters/verifiers/         GRPO / Verifiers RL adapter (step-first)
tests/                      adversarial + step suites
docs/format_judgement.md    OOXML + optional LLM rubrics
docs/roadmap.md             what shipped + what to do next (MCP, GDE, …)
```

## Verifiers adapter

```bash
uv pip install 'swivelbench[verifiers]'
python -c "from adapters.verifiers import load_environment; print(load_environment(['CB-SEED-001@S1_template']))"
python -m adapters.verifiers.smoke --task CB-SEED-001
```

Default `load_environment()` with `prefer_steps=True` loads Track A step
episodes. Reward = `criterion_pass_rate`; `task_passed` is in `reward_detail`.

## Provenance

Seed banking/grading fixtures are synthetic. The public-company catalog is a
scaffold for future real-filing ground truth (disabled until filled).

## License

MIT
