# SwivelBench status & roadmap

Living doc of what the structural overhaul shipped, what is still missing, and
recommended next work. Companion to the paper-backed design notes in
[README.md](../README.md).

Last updated: 2026-08-09 (strict pass contract, canonical result fields,
authority-floor oracle coverage, and live run-status reporting).

### Strict grading contract (current)

`task_passed` is the published grade and is true only when every active rubric
criterion passes. `criteria_passed` / `criteria_total` are exact counts;
`criterion_pass_rate` and `score_100` remain diagnostic and training signals.
Provider and harness failures are invalid runs and are excluded from model
aggregates.

### Current Nemotron grades (0–100)

Replay of prior successful OpenRouter rollouts through the post-overhaul verifier
(`eval/results/leaderboard.json`). Fresh CB rerun was rate-limited.

| Model | CB-SEED-001 | GR-SEED-001 | Mean | Task passed |
|---|---:|---:|---:|---|
| Oracle | 100 | 100 | 100 | yes / yes |
| Nemotron 3 Super 120B | **69** | **85** | **77** | no / no |

`score_100 = criterion_pass_rate × 100`. Task pass still requires all criteria.

---

## 1. What we did

### Scoring (RLVR rubrics)

- Removed `raw` / `final` / `KIND_SHARE` / `CRITICAL_CAP`.
- **`criterion_pass_rate`** — fraction of active criteria satisfied (dense RL reward).
- **`task_passed`** — true only if **all** criteria pass (published pass metric).
- Criteria metadata: `step=`, `level=` (tool|plan|adapt|ground|reason), `role=` (required|bonus|penalty).
- Format checks (`F*`) remain deterministic OOXML and participate equally in the rate.
- Optional LLM criteria stay **out** of the default score until they pass
  `eval/calibrate_criterion.py` (draft → hand-grade → judge agree → adversarial flip).

### Multi-step architecture

| Track | Unit | Purpose |
|---|---|---|
| **A (training)** | `CB-*@S*` / `GR-*@S*` | One fair prompt per workflow step; gold prefix state; no prior transcript |
| **B (eval)** | `CB-*` / `GR-*` E2E | Thin orchestrator prompt; composition / long-horizon |

CB steps: `S1_template` → `S2_products` → `S3_model` → `S4_spreading` → `S5_report` → `S6_customer_push` → `S7_systems`  
GR steps: `S1_rubric` → `S2_queue` → `S3_grade` → `S4_regrades`

### Harness / product surfaces

- Oracles refactored into per-step runners + snapshot prepare.
- Verifiers/GRPO adapter rewards `criterion_pass_rate`; prefers step episodes; logs `saturated_hint`.
- Adversarial + step + calibration tests green.
- README cites ComplexConstraints, FORCE-Bench, SARA, GDE papers.
- Localhost Environment Design header updated: **Criterion rate** + **Task pass/fail** (no RAW→FINAL / capped badge).
- Public-company catalog scaffold (`fixtures/public_companies.json`) — placeholders only.

### Papers we absorbed (short)

| Paper | Adopted idea |
|---|---|
| [ComplexConstraints / Expert Rubrics for RLVR](https://arxiv.org/abs/2606.09118) | Max viable atomicity, dense criterion rewards, all-criteria pass, judge calibration, Hierarchy L1–L5, GRPO |
| [FORCE-Bench](https://arxiv.org/abs/2607.19409) | Multi-dimension finance quality, task types, shared tools, domain rubrics |
| [SARA](https://arxiv.org/abs/2607.26253) | Avoid saturated GRPO groups; prefer short mixed-difficulty step episodes |
| [GDE / Office→SWE](https://arxiv.org/abs/2608.01604) | Nested goal loops; trajectory-level criterion fraction; keep long-horizon eval |

---

## 2. What we should do next

Rough priority: **P0** unblock training/eval honesty · **P1** capability depth · **P2** platform/integration.

### P0 — Finish the current design honestly

1. **Public companies & report types (catalog TBD)**  
   Decide tickers + report-type roster; fill `ground_truth_metrics`; enable catalog rows; seed multiple concurrent requests that need different templates; assert model cells against real public figures.

2. **Re-materialize / re-run baselines under the new scorer**  
   Historical traces can now be replayed into canonical strict results; fresh
   provider runs remain publishable only when they complete successfully.

3. **Wire live run scores into Environment Design**  
   Both domain benchmark cards now bind to `/api/runs` and display the selected
   canonical run's exact criterion count, diagnostic rate, validity, and PASS/FAIL.

4. **Fairness audit of every step prompt**  
   Self-containment test: oracle `task_passed` from step prompt + snapshot alone; traps discoverable in-world; graded checklist ↔ assert IDs 1:1; only the needed policy slice.

5. **Doc drift cleanup**  
   Current scoring docs now describe strict all-criteria passing; Phase 0 and
   pre-overhaul result notes are explicitly marked historical.

### P1 — Goal-directed execution (GDE)

Today GDE is **structural only** (steps ≈ nested goal loops; E2E ≈ composition; Hierarchy tags on criteria). We do **not** yet measure the four GDE behaviors.

**Build a GDE layer:**

| Behavior | What to instrument | Where it shows up |
|---|---|---|
| Goal formation | Did the agent pick the right subgoal for this step? | Step prompt adherence; required tools called before side effects |
| State construction | Did it gather/integrate the right env facts? | Read trails + groundedness criteria |
| Goal stability | Did later actions preserve earlier constraints? | Propagation / negative traps across steps on E2E |
| Verification | Did it check env evidence before finishing? | Spread check, re-read after write, mid-trajectory verify tools |

Deliverables:

- Trajectory diagnostics (eval-only first): per-run GDE scorecard beside `criterion_pass_rate`.
- Optional bonus criteria once calibrated (do not let process reward replace factual RLVR).
- Track B remains the transfer / composition suite; Track A remains the dense trainer.

### P1 — Document creation (deliverables quality)

We already write real `.xlsx` / `.docx` via tools and grade **structure**. Still missing:

1. **Numeric groundedness in prose** — memo/gradesheet numbers match model/DB (SQL where possible; LLM only after calibration).
2. **FORCE-style dimensions** (accuracy, groundedness, clarity, structure) as reporting axes — not one blob score.
3. **Template diversity for public cos** — distinct section contracts per report type.
4. **Artifact UX** — downloads, side-by-side oracle vs agent docs in viz, format-fail detail surfaces.
5. **Optional LLM rubric path** — keep behind `calibrated=true`; never sole signal for traps.

### P1 — MCP integration

**Today:** agents use OpenAI-style tool schemas (`envs/*/tools.py`) over local ActionAPI. Cursor chat can use MCP; the **benchmark does not**.

**Should do:**

1. Expose SwivelBench ActionAPI as an **MCP server** (stdio and/or HTTP) mirroring existing tools 1:1.
2. Keep SQL verifier as source of truth — MCP is a transport, not a new reward path.
3. Dual harness: OpenAI tools (current baselines) + MCP clients (Claude Code, Cursor agents, custom MCP runners).
4. Fairness: same allowlists, step tool subsets, and latency/step budgets across transports.
5. Document MCP install / smoke in README; add `adapters/mcp/` (or similar) with parity tests vs ActionAPI.

Aligns with GDE/LHMTA-style office agents that spoke MCP to tools.

### P2 — Training systems

1. **SARA-style rollout allocation** — abandon saturated step groups early; we only log `saturated_hint` today.
2. **Role-aware reward** — use `role_aware_reward(α, β)` deliberately once bonus criteria exist.
3. **Curriculum** — mix step difficulties; held-out step variants + disjoint E2E seeds for transfer claims.
4. **Snapshot/restore performance** — cheaper mid-episode resets for RL throughput.
5. **GRPO configs** — documented recipes (group size, which step pool, train vs eval task lists).

### P2 — Localhost / product polish

1. Keep viz server start documented; ensure score header + story copy never regress to RAW/FINAL.
2. Run picker shows `criterion_pass_rate` / `task_passed` natively (partially done in `viz/static`).
3. Step-episode explorer view (not only E2E graphs).
4. Prompt panel should show Track A step prompts when viewing step tasks, not only the old giant E2E string baked into Environment Design JS.

### P2 — Judgement & safety of the reward

1. Expand adversarial suite for new public-company traps and report types.
2. Calibrate any LLM criterion before merge; monitor reward hacking (verbosity, verbal satisfaction).
3. `finish` summary honesty vs DB — optional eval diagnostic (verifier still ignores transcript by design).

---

## 3. Explicit non-goals (until decided)

- Final public company / report-type roster (owner decision).
- Uncalibrated LLM criteria in default `task_passed`.
- Replacing SQL RLVR with pure LLM-as-judge.
- Full SARA allocator before we have scale pain.
- Per-tool dense reward shaping (GDE paper used trajectory-level fraction).

---

## 4. Suggested sequencing

```text
1. Public-company catalog + real-number asserts
2. Fresh baselines + live score binding in localhost
3. GDE diagnostics (eval-only scorecard)
4. MCP server adapter + parity tests
5. Document quality (groundedness) + calibrated LLM bonus
6. SARA + GRPO training recipes at scale
```

---

## 5. Quick reference — key paths

| Path | Role |
|---|---|
| `core/verifier.py` | Rubric scoring |
| `core/steps.py` | StepSpec / StepTask primitives |
| `envs/*/steps.py` | Fair step prompts + oracle step runners |
| `envs/commercial_banking/public_companies.py` | Public-co scaffold |
| `eval/calibrate_criterion.py` | LLM verifier calibration loop |
| `adapters/verifiers/` | GRPO / Verifiers RL adapter |
| `Swivelbench Environment Design/*.dc.html` | Localhost explorers |
| `docs/format_judgement.md` | OOXML + optional LLM rubrics |

---

## 6. How to check health

```bash
python3 eval/oracle.py --task CB-SEED-001          # task_passed
python3 eval/oracle.py --task CB-SEED-001@S3_model
python3 -m pytest tests/test_adversarial.py tests/test_steps.py tests/test_calibration_public.py -v
python3 -m eval.calibrate_criterion --demo
python3 -m viz.server --port 8765                  # http://127.0.0.1:8765/
```
