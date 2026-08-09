# Environment graphs — SwivelBench dual domains

Sketch-aligned workflows scored by deterministic SQL over two ATTACHed SQLite
databases. Agent runtime is a multi-turn tool loop (not an executable graph).

## Shared harness

```mermaid
flowchart TB
  subgraph harness [Shared Harness]
    TaskSpec[Task prompt plus policy]
    ActionAPI[Typed ActionAPI no raw SQL]
    DualDB["SQLite A ATTACH B"]
    Verifier["assertions.sql rubric criteria"]
    Trace[In-memory action trace]
    TaskSpec --> ActionAPI
    ActionAPI --> DualDB
    ActionAPI --> Trace
    DualDB --> Verifier
  end
```

## Commercial banking (`envs/commercial_banking`)

Systems: `credit_workbench` (A) + `ncino_core` (B). Tasks: `CB-*`.

```mermaid
flowchart TD
  trigger[Credit request] --> analyst[Analyst]
  analyst --> chooseFmt[Locate and choose report format]
  chooseFmt --> pullCov[Pull covenants and credit products]
  analyst --> pullDeals[Pull older deals and materials]
  pullDeals --> think[Think through covenants and pricing]
  analyst --> pullFin[Pull financials from web and news]
  pullFin --> excel[Create Excel models]
  excel --> sendSpread[Send to spreading team]
  sendSpread --> checkSpread[Check financials when returned]
  checkSpread --> writeReport[Write report section by section]
  chooseFmt --> writeReport
  think --> writeReport
  writeReport --> formatOk[Format correctly]
  formatOk --> pushNCino[Push deal through nCino]
  pushNCino --> updateSys[Update covenants pricing systems]
```

Mess traps: corrupted templates, conflicting digests, spread injection,
archived customer duplicates, matured products, authority floor.

## Grading (`envs/grading`)

Systems: `inbox` (A) + `gradescope` (B). Tasks: `GR-*`.

```mermaid
flowchart TD
  getRubric["Get instructions and rubrics from prof email"] --> openGS[Open Gradescope homeworks exams]
  openGS --> gradeEach["Grade each - handwriting unclear answers"]
  gradeEach --> regrade[Deal with regrade requests]
```

Mess traps: conflicting/messy rubric emails, unclear answers, handwriting
noise, name-collision students, out-of-rubric regrade bait.

## Scoring

Every active SQL or format criterion participates in the rubric. A run is
published as `task_passed` only when all active criteria pass and at least one
criterion was evaluated. `criterion_pass_rate` is the dense diagnostic/RL
reward; it never turns a partial run into a pass. Exact counts are exposed as
`criteria_passed` and `criteria_total`.

## Per-step grade inventory

Every graph step has **multiple** SQL facets (template + digest provenance +
spread linkage + report completeness, etc.). Canonical assert IDs and SQL
intents live in:

- `envs/commercial_banking/fixtures/assertions.sql` (CB-SEED-001)
- `envs/grading/fixtures/assertions.sql` (GR-SEED-001)

Live breakdown: canvas
`canvases/swivelbench-environment-overview.canvas.tsx`.

BTB inspiration (concepts only, no LLM judge): structural completeness, data
provenance, and model↔spread linkage from bankertoolbench judge-guidance —
encoded as dual-DB boolean SELECTs under the rubric criteria.
