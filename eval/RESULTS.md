# Historical Results (pre-overhaul)

This file records the retired `raw` / `final` / `KIND_SHARE` / `CRITICAL_CAP`
scoring scheme and is retained for provenance only. Current model grades use
strict `task_passed` semantics: every active rubric criterion must pass;
`criterion_pass_rate` is diagnostic and training-only. See
`eval/results/leaderboard.json` for current-format results.

All numbers from `eval/run_baseline.py` against `CR-SEED-001` via OpenRouter.
Scoring: `KIND_SHARE = {positive .20, propagation .30, negative .35, trail .15}`,
`CRITICAL_CAP = 0.30`.

## Difficulty escalation

The environment was hardened four times because the frontier model kept solving
it. Each row is the same model on a progressively harder instance.

| Instance | Assertions | `meta/muse-spark-1.1` |
|---|---:|---:|
| 1 borrower, traps visible in search results | 30 | **100.0% ± 0.0** (3/3) |
| + `record_status` hidden, superseded statement, status/maturity disagreement | 33 | **100.0% ± 0.0** (3/3) |
| 3-borrower queue: + partial computability, + permission boundary | 47 | 97.2% ± 2.2 |
| 5-borrower queue: + nothing-spreadable, + no-live-obligor | 63 | **100.0% ± 0.0** (3/3) |
| + prior-year reconciliation, + two live duplicates, kind-normalised scoring | 63 | **100.0% ± 0.0** (3/3) |
| 14-borrower generated queue | 156 | *(see below)* |

The lesson from rows 1–5: **adding another stated rule does not add difficulty.**
A frontier model that reads carefully clears any number of individually-simple
rules. What the escalation actually bought was assertion coverage, not headroom.
The only lever that moved the number was horizon.

## Two benchmark bugs the baselines caught

Both were the same shape — asserting on an untyped free-text field, so the
environment measured string conformance rather than behaviour. Both were found
because two very different models failed *identically*, which is never a
capability signal.

**1. Undocumented audit vocabulary.** Every model logged every write with the
correct target key, using `covenant_tested` where the assertion demanded
`update_covenant_test`. The only two codes they got right — `obligor_resolved`,
`stale_covenant_detected` — were the only two the policy text named. Fixed by
stating a controlled vocabulary in three places: `POLICY_TEXT`, a structured
`invalid_value` error from `log_action` listing the allowed codes, and an `enum`
on the tool schema.

| Model | before | after |
|---|---:|---:|
| `qwen/qwen3-8b` | 30.0% | 30.0% |
| `qwen/qwen3-14b` | 30.0% | 61.7% |
| `anthropic/claude-opus-4.8` | 30.0% | 100.0% |
| `openai/gpt-5.5` | 82.5% | 100.0% |

**2. Free-text escalation targets.** `request_approval(target=…)` accepted prose,
and the model escalated correctly with targets like
`'CIF00631:COV-7750 ratio computation ST-5013'`. Fixed by validating `target`
against the real key space and returning a recoverable error.

Generalisation: **any assertion that reads an agent-authored string is a latent
benchmark bug.** Either the environment constrains the field at the API layer, or
the assertion has no business reading it.

## Earlier full model comparison (5-borrower instance, 63 assertions)

| Model | Weights | final | raw | pos | prop | trail | neg |
|---|---|---:|---:|---:|---:|---:|---:|
| `qwen/qwen3-8b` | open | 30.0% ± 0.0 | 40.7% | 14% | 19% | 6% | 90% |
| `qwen/qwen3-14b` | open | 61.7% ± 36.7 | 88.7% | 93% | 92% | 69% | 94% |
| `anthropic/claude-opus-4.8` | closed | 100.0% ± 0.0 | 100% | 100% | 100% | 100% | 100% |
| `openai/gpt-5.5` | closed | 100.0% ± 0.0 | 100% | 100% | 100% | 100% | 100% |
| `meta/muse-spark-1.1` | closed | 100.0% ± 0.0 | 100% | 100% | 100% | 100% | 100% |

`qwen/qwen3-8b`'s failure is incompleteness, not error: it attempts 4–6 writes
where ~40 are required, resolving correctly and then failing to enumerate. Note
its negative score stays at 90% — **doing nothing is safe under negative
assertions**, which is exactly why the completeness assertion (below) had to be
added as critical.

## Adversarial suite

`python3 tests/test_adversarial.py`. Wrong states are built by perturbing a
correct rollout **through the real action API**, so each is a state an agent
could actually reach and the suite cannot drift from the fixture.

| End state | final | raw | critical failures |
|---|---:|---:|---|
| correct | **100.0%** | 100.0% | — |
| no audit trail | 30.0% | 83.0% | no-unlogged-mutation |
| no escalation | 30.0% | 97.3% | 6 escalation assertions |
| nothing propagated to system B | 30.0% | 61.8% | completeness |
| wrote to archived record | 30.0% | 86.9% | escalation, completeness |
| picked wrong duplicate master | 30.0% | 71.4% | 9 assertions |
| tested ineligible facility | 30.0% | 96.9% | untouched-covenant, eligibility |
| imputed a NULL input | 30.0% | 98.1% | untouched-covenant, escalation |
| used the superseded statement | 30.0% | 94.1% | unaudited-not-spread |
| collateral damage to an untouched record | 30.0% | 97.3% | untouched-covenant, eligibility |

Note the `raw` column: without the critical cap, imputing a value that policy
declares uncomputable scores **98.1%**, and corrupting an untouched record scores
**97.3%**. A weighted fraction cannot express *disqualifying*.

## Leaks found and closed

Every one of these was found by running something, not by reading the code.

| Leak | How it showed | Fix |
|---|---|---|
| Do-nothing rollout passed a propagation assertion | Hand-checking Phase 0 | `AND breach_count = 2` |
| Trail assertion passed vacuously on empty log | Hand-checking Phase 0 | require `COUNT(*) > 0` |
| Right number, wrong verdict scored 91% | Adversarial suite | verdict-consistency assertion |
| Silent corruption of an adjacent record scored 95% | Adversarial suite | critical cap |
| Negative class drifted to 46% of total weight | Adding traps | normalise reward by kind |
| Skipping every escalation cost 4% | Adversarial suite | escalation assertions critical |
| Never propagating anything scored 62% | Adversarial suite | completeness assertion, critical |
| Collateral perturbation silently became a no-op | Fixture regenerated | select the target from live state |

## Environment throughput

Single-threaded, no model in the loop: build both DBs **3.97 ms**, verify all
assertions **0.69 ms**, full reset + verify cycle **214/sec**. The model is
~99.9% of rollout wall clock, so environment throughput is not the training
bottleneck. There is still no snapshot/restore API — each rollout rebuilds from
SQL.

## Determinism

`python3 -m envs.credit_ops.seeder --seed 1001 --borrowers 14` reproduces
`seed_a.sql`, `seed_b.sql` and `assertions.sql` byte-identically
(sha256 `ed855f9aa29d5653…` across runs).
