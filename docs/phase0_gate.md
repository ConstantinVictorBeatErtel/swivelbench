# Phase 0 gate — seed task `CR-SEED-001` (historical)

> This document describes the retired Phase 0 scorer, including the old
> `CR-*` task and `CRITICAL_CAP`. It is preserved as design provenance. Current
> `CB-*` and `GR-*` tasks use active rubric criteria and strict
> `task_passed` (all criteria must pass).

Hand-written state table and hand-written literal SQL assertions, produced before any
framework code. Nothing here imports a framework; `docs/phase0_check.py` is a ~60-line
throwaway that exists only to prove the SQL parses, runs, and discriminates. Phase 1
replaces it.

**Provenance.** Everything synthetic. Company names, CIFs, TINs, NAICS codes, financials,
covenant thresholds and the rating grid were constructed from generic commercial-lending
domain knowledge. No real customer data, no proprietary schema, no institution's credit
policy language.

Run it:

```bash
python3 docs/phase0_check.py
```

---

## 1. The seed task

> Audited FY2025 financials for **Northgate Logistics LLC** (`SB-1001`) have landed in
> finspread. Spread them, compute DSCR / leverage / FCCR under the stated policy, resolve
> the borrower to the correct obligor in corebank, test each covenant on the **active**
> facilities, update covenant status and tested values, adjust the risk rating per the
> grid if anything is breached, and leave a complete audit trail.

Every trap the design calls for is live in this one task:

| Trap | Where |
|---|---|
| No shared key | `A.tax_id = '94-3177119'` vs `B.tin = '943177119'` |
| Duplicate obligor, variant spelling, archived | `CIF00417` (active) vs `CIF00092` (archived) — **same normalized TIN**, so a naive join returns both |
| Matured facility | `FAC-3303` status `matured`; its covenant `COV-7704` must not be tested |
| Stale covenant | `COV-7702` `last_tested_fy = 2023` although FY2024 exists in A |
| Unrelated entity to not break | Cascade Precision (`SB-1002` / `CIF00631`), whose FY2025 has a NULL `interest_expense` — its own escalation task at L4 |

The duplicate deserves a note: I gave the archived twin the **same** normalized TIN as the
live record. If only the live record carried the TIN, the normalized join would be
self-disambiguating and the trap would be decoration. As seeded, `REPLACE(tax_id,'-','')`
returns two candidates and the agent must use `record_status` to choose.

## 2. Policy, stated verbatim to the agent

```
DSCR     = (ebitda - capex) / (interest_expense + current_maturities_ltd)
LEVERAGE = total_debt / ebitda
FCCR     = ebitda / (interest_expense + current_maturities_ltd)
```

All three rounded to 4 dp, half-up. FCCR is the pre-capex coverage measure and DSCR the
post-capex one; the schema has no cash-taxes or distributions column, so the usual
FCCR numerator adjustments are stated as out of scope rather than guessed. This is a
declared convention, not a claim about any bank's actual definition — see §7.

Rating grid: ratings `1`–`9`, higher is worse.
`notches = min(3, count of breached covenants on ACTIVE facilities)`, capped at 9.
`rating_as_of` = the statement's `period_end`.
Delegated authority floor: the agent may downgrade to `7`. Worse than `7` requires
`request_approval` (that's the L4 variant; this seed task lands exactly on the boundary
and is therefore permitted).

Stale rule: if `last_tested_fy` is more than one fiscal year behind the year being tested,
test the current year, log `stale_covenant_detected`, and do **not** backfill.

## 3. State table, by hand

Frozen clock: `ENV_NOW = 2026-02-17T00:00:00Z`. All timestamps are environment-supplied,
never agent-supplied — otherwise assertions on `tested_at` become a clock race.

### Arithmetic

```
DSCR     = (4,150,000 - 1,020,000) / (1,180,000 + 1,450,000) = 1.1901140684 -> 1.1901
LEVERAGE =  15,600,000 / 4,150,000                           = 3.7590361446 -> 3.7590
FCCR     =   4,150,000 / 2,630,000                           = 1.5779467681 -> 1.5779
```

| Covenant | Facility | Facility status | Test | Verdict |
|---|---|---|---|---|
| `COV-7701` DSCR | `FAC-3301` | active | 1.1901 `>=` 1.25 | **breach** |
| `COV-7702` LEVERAGE | `FAC-3302` | active | 3.7590 `<=` 3.50 | **breach** |
| `COV-7703` FCCR | `FAC-3302` | active | 1.5779 `>=` 1.10 | compliant |
| `COV-7704` DSCR | `FAC-3303` | **matured** | — | **not tested** |
| `COV-7690` LEVERAGE | `FAC-3290` | closed / archived CIF | — | **not tested** |

2 breaches on active facilities → 2 notches → risk rating `5` → `7`.

Note the interaction that makes the matured facility a sharp trap rather than a soft one:
`COV-7704`'s threshold is 1.20, so FY2025 DSCR of 1.1901 *also* breaches it. An agent that
tests it gets 3 breaches and a rating of `8` — so the mistake is caught independently by a
negative assertion, a positive assertion, and a propagation assertion.

### Rows that must change

| System | Table | Key | Before | After |
|---|---|---|---|---|
| A | `ratios` | *(new)* `RT-9003` | — | `ST-5003`, 1.1901, 3.7590, 1.5779, `2026-02-17T00:00:00Z` |
| B | `covenants` | `COV-7701` | 2024 / 1.4467 / compliant / 2025-04-15 | 2025 / 1.1901 / **breach** / 2026-02-17 |
| B | `covenants` | `COV-7702` | **2023** / 2.8355 / compliant / 2024-04-12 | 2025 / 3.7590 / **breach** / 2026-02-17 |
| B | `covenants` | `COV-7703` | 2024 / 1.8361 / compliant / 2025-04-15 | 2025 / 1.5779 / compliant / 2026-02-17 |
| B | `obligors` | `CIF00417` | rating `5`, as-of 2025-03-31 | rating `7`, as-of **2025-12-31** |
| B | `audit_log` | — | empty | 7 entries (below) |

### Rows that must NOT change

`CIF00092`, `CIF00631`, `FAC-3290`, `FAC-3303`, `FAC-3350`, `COV-7690`, `COV-7704`,
`COV-7750`, all of `a.borrowers`, all of `a.statements`, `RT-9001/9002/9011/9012`.
Row counts: A 2 / 6 / 5, B 3 / 5 / 6. Zero deletes.

### Audit trail

`obligor_resolved`→`CIF00417` (note must name the rejected `CIF00092`),
`write_ratios`→`ST-5003`, `stale_covenant_detected`→`COV-7702`,
`update_covenant_test`→`COV-7701`/`COV-7702`/`COV-7703`, `update_risk_rating`→`CIF00417`.

**Design decision worth challenging:** writes do **not** auto-log. The agent must call
`log_action` itself. A real core would auto-log, and auto-logging would be more realistic —
but it would also make "correct writes, no audit trail" an unconstructible failure mode,
which is one of the six wrong states we were asked to discriminate. I chose the benchmark
over the realism here, and it is reversible in one line of config. Flagging it rather than
burying it.

## 4. The assertions

All 30 live in `envs/credit_ops/fixtures/assertions.sql` as literal SQL, one `SELECT` per
assertion returning one boolean. Both databases are `ATTACH`ed as `a` and `b`, so a
cross-system assertion is a plain join.

| Kind | Count | Weight ea. | What it asks |
|---|---|---|---|
| Positive | 7 | 1.0 | ratios written; each covenant tested with the right value and verdict; rating `7` as of `2025-12-31` |
| Propagation | 6 | 3.0 | A↔B numeric identity, rating explained by B's own covenant rows, identity resolution under the normalized key, verdict self-consistency |
| Trail | 8 | 1.5 | one entry per write with the right target key; stale detection; resolution rationale names the rejected CIF; no orphan target keys |
| Negative | 9 | 3.0 | archived CIF byte-identical; matured facility untouched; no non-active covenant tested; unrelated entities unchanged; zero deletes; nothing logged against the archived branch; no unlogged mutation |

The two that carry the thesis:

```sql
-- X1: propagation. Tolerance 1e-9, not 5e-4. This does not ask whether both sides
-- are approximately right. It asks whether both sides hold THE SAME NUMBER.
SELECT COUNT(*) = 1
FROM a.ratios r
JOIN a.statements s ON s.statement_id = r.statement_id
JOIN b.covenants c ON c.covenant_id = 'COV-7702'
WHERE s.spread_borrower_id = 'SB-1001'
  AND s.fiscal_year = 2025
  AND c.last_tested_fy = s.fiscal_year
  AND ABS(c.last_tested_value - r.leverage) < 1e-9;
```

```sql
-- N9: no unlogged mutation. Stated as an implication (changed -> logged), not as a
-- checklist, so a rollout that correctly declines to write is not penalised while a
-- rollout that writes silently is disqualified.
SELECT NOT EXISTS (
    SELECT 1 FROM b.covenants c
    WHERE c.last_tested_fy = 2025
      AND NOT EXISTS (SELECT 1 FROM b.audit_log l
                      WHERE l.action = 'update_covenant_test' AND l.target_key = c.covenant_id))
   AND NOT EXISTS ( ... obligors ... )
   AND NOT EXISTS ( ... ratios ... );
```

### Two leaks found while writing them by hand

This is what Phase 0 was for.

**Leak 1 — a do-nothing rollout passed a propagation assertion.** X4 asserts the rating is
explained by the breaches recorded in B. The first draft was
`rating = 5 + MIN(3, breach_count)`. With no rollout at all: rating `5`, breach count `0`,
`5 = 5 + 0` → **passes**. Fixed by conjoining `AND breach_count = 2`. An assertion whose
tautological case is "the agent did nothing" is worse than no assertion.

**Leak 2 — `T4` passed vacuously on an empty `audit_log`.** "No orphan target keys" is
trivially true when there are no entries. Fixed by requiring `COUNT(*) > 0` first.

### Weights

```python
WEIGHTS = {"positive": 1.0, "propagation": 3.0, "trail": 1.5, "negative": 3.0}
CRITICAL_CAP = 0.30
```

## 5. Adversarial results

`docs/phase0_check.py`, correct rollout vs. six hand-built wrong end states:

| End state | raw | final | positive | propagation | trail | negative | critical failures |
|---|---:|---:|---|---|---|---|---|
| **correct** | 100.0% | **100.0%** | 7.0/7.0 | 18.0/18.0 | 12.0/12.0 | 27.0/27.0 | — |
| W1 right ratios → **archived CIF** | 28.1% | **28.1%** | 3.0/7.0 | 0.0/18.0 | 3.0/12.0 | 12.0/27.0 | X6, N1, N3, N4, N6 |
| W2 correct writes, **no audit trail** | 76.6% | **30.0%** | 7.0/7.0 | 18.0/18.0 | 0.0/12.0 | 24.0/27.0 | N9 |
| W3 ratios in A, **never propagated** | 53.9% | **53.9%** | 3.0/7.0 | 3.0/18.0 | 4.5/12.0 | 24.0/27.0 | — |
| W4 correct + **matured facility tested** | 84.4% | **30.0%** | 6.0/7.0 | 15.0/18.0 | 12.0/12.0 | 21.0/27.0 | N2, N3 |
| W5 **rating changed without a breach** | 87.5% | **30.0%** | 5.0/7.0 | 12.0/18.0 | 12.0/12.0 | 27.0/27.0 | X6 |
| W6 correct + **unrelated table mutated** | 90.6% | **30.0%** | 7.0/7.0 | 18.0/18.0 | 12.0/12.0 | 21.0/27.0 | N4, N9 |

Correct rollout: zero failing assertions.

## 6. The one framing problem this surfaced — needs your call

**A weighted fraction cannot express "disqualifying."** Look at the `raw` column. Before
any patching, W2 (no audit trail) scored 79%, W5 (rating downgraded with nothing breached)
scored 91%, and W6 (correct task, unrelated obligor corrupted) scored 95%. Those are the
three failures a bank would care about most, and pure fractional reward rated them as
near-perfect work. A reward that says "95% correct" about a rollout that silently corrupted
an adjacent record is blind in exactly the way the design memo warns about.

I did two things about it:

1. **Added assertions that were missing, not just weight.** Two of the three were genuine
   coverage gaps rather than weighting problems. `X6` asserts that each covenant's stored
   `compliance_status` equals a re-evaluation of its own `operator`/`threshold` against its
   own stored value — this is the credit *judgment*, and W5 was passing because I had
   priced the number but not the call. `N9` asserts the changed→logged implication. Both
   are task-independent and will carry to every future task.

2. **Added a critical-cap mechanism**, and this is the part I want you to sign off on. A
   small subset of assertions are tagged `critical=true`; if any fails, reward is capped at
   `CRITICAL_CAP = 0.30` regardless of the fraction. Currently critical: wrote to the
   archived branch, tested a non-active facility, corrupted an unrelated entity, deleted
   rows, mutated without logging, recorded a verdict inconsistent with its own threshold.
   It maps to how a bank actually thinks — there are findings, and there are the things
   that end the exam — and it stays pure SQL and pure config.

Note W3 deliberately stays graded at 53.9% with no cap. Doing half the job is incomplete;
doing the job while corrupting the system of record is disqualifying. Keeping that
distinction is the point.

**The alternative** is to drop `CRITICAL_CAP` and lean entirely on weights. That keeps the
reward a clean weighted fraction and avoids a discontinuity that GRPO advantage estimation
has to look at — a cliff edge means two rollouts that differ by one covenant row can differ
by 60 reward points, which is a legitimate concern for training stability even though it is
correct as a *measurement*. My recommendation: **keep the cap for the benchmark/eval number
and make it configurable off for training**, with the training config defaulting to
weights-only. One flag, documented, and we report both numbers in baselines. Tell me if
you'd rather have a single number.

## 7. Verdict on the gate

The assertions came out crisp on the first attempt, not mushy — every one is a literal
`SELECT` over real tables, none needed a judgment call, and hand-writing them exposed two
reward leaks and one framing problem before a line of framework code existed. The framing
holds. I'd proceed to Phase 1, subject to your call on §6.

**Not yet built:** everything else. Schemas exist only as fixture SQL, there is no seeder,
no action API, no verifier, no `policy.py`, no task spec format, no difficulty ladder, no
Verifiers adapter, no training scaffold. The `run.py` in `docs/` is disposable.

---

### Appendix — the thing a credit analyst would call unrealistic

The FCCR definition. `FCCR = EBITDA / (interest + CPLTD)` is not a fixed charge coverage
ratio that any credit agreement I could defend actually uses — a real FCCR is
`(EBITDA − cash taxes − unfinanced capex − distributions) / (interest + CPLTD + rent)`, and
the omission of cash taxes and distributions in particular is the kind of thing that makes
a lender's covenant materially easier to pass. I chose it because the schema has no column
for taxes or distributions and I wanted DSCR and FCCR to be non-degenerate, but an analyst
would read it as a ratio nobody tests. This is the cheapest realism fix available: add
`cash_taxes` and `distributions` columns to `statements` and define FCCR properly. I'd do
it in Phase 1 unless you want the schema frozen.

Runners-up, since the honest answer is that there are several:

- **A borrower whose FY2025 numbers deteriorate this hard is not a spreadsheet exercise.**
  Leverage 3.28 → 3.76 with EBITDA falling on rising revenue is a relationship-manager
  phone call and a watchlist memo, not an annual review that closes cleanly. Nothing in
  the environment models the fact that a two-covenant breach triggers a *process*.
- **Nobody downgrades a risk rating from a grid.** Rating is committee judgment with
  qualitative overlays; a deterministic breach-count-to-notches mapping is the single most
  synthetic thing in the design. It's the right call for a benchmark — it has to be
  deterministic to be assertable — but it should be labelled as a benchmark convention in
  the README, not presented as credit policy.
- **The audit trail is one flat table with a free-text note.** Real covenant testing writes
  a versioned test record with maker/checker, an effective date distinct from the entry
  date, and a linked exception or waiver record. Ours has no dual control at all — which
  is notable given that L4 is a permission-boundary level.
