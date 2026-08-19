# SwivelBench Environment Content v1

Status: implementation specification
Version: `v1`
Freeze date: `2026-08-18`
Owner: SwivelBench benchmark maintainers

This document is the content contract for the first production-shaped
SwivelBench corpus. It is intentionally separate from the smoke-test fixtures
under `envs/*/fixtures/`. The smoke fixtures test harness wiring; this corpus
tests whether an agent can do useful, evidence-grounded enterprise and
academic work across varied worlds.

No corpus artifact is benchmark-eligible until it has a manifest, provenance,
structured gold, deterministic validation, and a release decision. A model
may propose content, but a model response is never itself evidence of
correctness.

## 1. Readiness definition

The environment is ready only when all of the following are true:

1. The SEC snapshot can be restored without network access and every released
   financial fact traces to a filing, accession, XBRL concept, context, unit,
   and hash-verified source artifact.
2. Every commercial-credit report type has a complete ordered outline, a
   structured specification, a rendered template, required evidence, and
   type-aware verifiers.
3. Every academic assessment has an original problem set, answer key,
   rubric, instructions, grading world, and visible submissions whose scores
   are derivable from the visible work.
4. Train, validation, and test splits have no duplicated question templates,
   source facts, or hidden identifiers that predict gold.
5. Independent solvers agree on all released keys; disagreements are
   quarantined or adjudicated with an explicit decision record.
6. Public manifests contain no private answer key or gold state.
7. Oracle, idle-agent, adversarial, provenance, licensing, render, and
   offline-restore gates pass in clean CI.

The current `*-SEED-001` tasks remain wiring anchors. They are not counted in
the V1 corpus and must not be used as evidence of content diversity.

## 2. V1 scope and counts

### 2.1 Banking

V1 contains 20 non-financial public companies across ten sectors:

| Sector | Train | Validation | Test |
|---|---|---|---|
| Software | ADBE, ORCL |  |  |
| Retail | COST, WMT |  |  |
| Transportation | DAL, UPS |  |  |
| Industrials | CAT, DE |  |  |
| Utilities | NEE, DUK |  |  |
| Healthcare | HCA, CVS |  |  |
| Consumer staples |  | KO | PEP |
| Materials |  | NUE | DOW |
| Telecommunications |  | VZ | T |
| Automotive |  | F | GM |

For each company, V1 stores the latest three eligible 10-K filings and latest
two eligible 10-Q filings accepted on or before the freeze date. The raw
snapshot is a versioned release artifact; hashes, manifests, normalized facts,
and selected excerpts are committed to the repository.

There are four report families and three scenario variants:

- `AR`: annual review
- `NM`: new-money underwriting
- `AW`: amendment/waiver
- `WL`: watchlist/early warning
- `BASE`: clean evidence and ordinary authority
- `REC`: stale/amended/unit/context reconciliation
- `ADV`: authority escalation plus distractor, injection, identity, or bad
  template

The target is `20 × 4 × 3 = 240` banking tasks, with 80 structured base
cases and 80 reference reports. Variants share real filing evidence but have
different synthetic facilities, policies, and expected actions.

### 2.2 Academic grading

V1 contains eight original courses:

- Train: Calculus I, Introductory Statistics, Programming with Python,
  Microeconomics, Financial Accounting
- Validation: Linear Algebra
- Test: University Physics: Mechanics, Data Structures and Algorithms

Each course contains five assessments:

| Assessment | Questions per assessment |
|---|---:|
| Problem Set 1 | 6 |
| Problem Set 2 | 8 |
| Quiz | 5 |
| Midterm | 8 |
| Final | 10 |

V1 therefore targets 40 assessments, 296 original questions, eight
submissions per assessment, 320 submission packages, and 2,368 question-level
response instances. Counts are release-manifest assertions, not informal
aspirations.

## 3. Rights and provenance policy

The repository and generated distributable corpus are MIT-compatible and
commercial-safe.

- SEC government data is stored with source URLs, access dates, accession
  numbers, and hashes. The corpus does not imply SEC endorsement.
- Educational sources are research references by default. The research model
  may summarize a source's topics, learning objectives, assessment patterns,
  and misconceptions, but may not copy question text, solutions, diagrams, or
  distinctive phrasing into a released artifact.
- A source with noncommercial, ShareAlike, or ambiguous terms is marked
  `research_only` and cannot be used as a direct or closely adapted content
  source for the distributable corpus.
- Public-domain or commercially compatible sources may be quoted only when
  the source record permits it and attribution is retained.
- Every source has a `SourceRecord`: URL, publisher, title, access date,
  license, permitted use, local artifact path, hash, and notes.
- Every generated file has a provenance record containing the source IDs,
  blueprint ID, model ID/version, prompt hash, deterministic seed, renderer
  version, and review decisions.
- A similarity/originality scan is a release gate. A suspected close match is
  quarantined for human review.

## 4. SEC acquisition and evidence contract

The acquisition process uses SEC `data.sec.gov` submissions and Company Facts
APIs plus EDGAR archive documents. It must send an identifying `User-Agent`,
cache every response, back off on errors, and remain below the SEC's published
ten-requests-per-second ceiling. Scored episodes never call the network.

For each company, acquire:

- `submissions/CIK##########.json`
- `companyfacts/CIK##########.json`
- filing index metadata for each selected 10-K/10-Q
- the primary inline-XBRL/HTML document
- required XBRL instance/linkbase artifacts when the fact cannot be resolved
  from Company Facts alone

Each selected filing is represented as:

```json
{
  "company_id": "PUB-ADBE",
  "ticker": "ADBE",
  "cik": "0000796343",
  "accession": "0000796343-25-000012",
  "form": "10-K",
  "filed_date": "2025-01-30",
  "period_end": "2024-11-29",
  "primary_document": "...",
  "primary_sha256": "...",
  "companyfacts_sha256": "...",
  "source_url": "https://www.sec.gov/Archives/..."
}
```

Normalize at least revenue, operating income, net income, cash, current
assets/liabilities, total assets, short- and long-term debt, interest expense,
operating cash flow, capital expenditure, depreciation/amortization where
available, and equity. Each normalized fact stores taxonomy, concept, unit,
instant/duration context, start/end dates, accession, form, filing date,
source artifact, extraction method, and confidence.

Fact selection is deterministic:

- Prefer facts from the selected filing and period.
- Prefer standard taxonomy concepts over company extensions when meaning is
  equivalent.
- Never combine incompatible duration or instant contexts.
- Normalize units explicitly; never infer a scale from a label alone.
- Prefer an accepted amendment over an earlier filing according to the
  recorded precedence rule.
- If a metric cannot be supported, mark it unavailable rather than substitute
  an unannounced proxy.

Derived metrics store formulas and input fact IDs. EBITDA is only derived from
supported operating income plus supported depreciation/amortization; otherwise
the scenario uses an alternate supported metric or declares EBITDA unavailable.

## 5. Report specifications

Each report specification is JSON-backed and contains ordered sections,
required evidence, calculations, permitted claims, policy rules, negative
traps, format requirements, and verifier IDs.

### Annual Review (`AR`)

1. Decision Header
2. Relationship and Exposure Summary
3. Borrower and Business Overview
4. Industry and Competitive Position
5. Historical Financial Performance
6. Leverage, Coverage, and Cash Flow
7. Liquidity and Debt Maturities
8. Covenant Compliance and Headroom
9. Risk Rating Assessment
10. Key Risks and Mitigants
11. Recommendation and Conditions
12. Sources and Filing Provenance

### New-Money Underwriting (`NM`)

1. Decision Header
2. Request and Proposed Structure
3. Borrower, Ownership, and Management
4. Purpose and Sources/Uses
5. Business and Industry Analysis
6. Historical Financial Performance
7. Base and Downside Projections
8. Primary and Secondary Repayment Sources
9. Leverage, Coverage, and Liquidity
10. Collateral and Enterprise Support
11. Covenants and Reporting Requirements
12. Policy Exceptions
13. Key Risks and Mitigants
14. Recommendation, Conditions, and Approval Routing
15. Sources and Filing Provenance

### Amendment/Waiver (`AW`)

1. Decision Header
2. Existing Exposure and Original Approval
3. Requested Amendment or Waiver
4. Cause and Management Explanation
5. Performance Since Approval
6. Covenant Breach and Pro Forma Headroom
7. Liquidity, Debt Maturities, and Repayment Capacity
8. Pricing, Fees, and Consideration
9. Downside and Exit Analysis
10. Risk Rating Impact
11. Conditions, Reporting, and Remediation
12. Recommendation
13. Sources and Filing Provenance

### Watchlist/Early Warning (`WL`)

1. Decision Header
2. Watchlist Trigger and Event Timeline
3. Current Exposure
4. Operating and Financial Trend Analysis
5. Liquidity Runway
6. Debt Maturities and Refinancing Risk
7. Covenant Forecast
8. Management Response
9. Risk Rating or Classification Rationale
10. Monitoring Plan and Cadence
11. Lender Action Plan
12. Recommendation
13. Sources and Filing Provenance

The four report types must have distinct required evidence and cannot be
validated by one hardcoded heading list. A rendered DOCX is generated by a
deterministic renderer from the report specification and structured section
data.

## 6. Academic content contract

Each course has a course specification, instruction policy, misconception
library, assessment blueprints, original questions, answer keys, rubrics,
submission profiles, and grading-world manifest.

Question types include numeric, symbolic, selected response, structured
explanation, proof/derivation, graph/diagram, table/ledger, code writing,
code tracing, algorithm analysis, and error correction.

Each question includes:

- learning objective and difficulty
- original prompt
- canonical solution
- accepted equivalent forms and tolerances
- independent rubric criteria
- required reasoning atoms
- common misconceptions
- disallowed shortcuts
- rendering requirements

Each assessment has its own allowed-resource, notation, rounding, proof/code,
partial-credit, late-work, resubmission, and regrade instructions. Authority
changes and corrections are delivered through realistic email threads.

Each assessment gets eight rotated student profiles:

1. Fully correct and clear
2. Correct method with arithmetic error
3. Conceptual misconception
4. Partially complete
5. Wrong method with coincidentally correct result
6. Correct reasoning with transcription/unit/notation error
7. Blank/off-topic/incomplete
8. Ambiguous/noisy/difficult-to-read

The profile is not encoded in the task ID or filename. Structured responses are
rendered into typed PDFs, handwriting-style scans, diagrams, code, ledgers,
and multi-page exams. The visible artifact—not hidden metadata—must determine
the released grade.

## 7. Model-production workflow

The pipeline is a resumable state machine:

`research_pending → researched → blueprint_approved → generated → solved →
reviewed → rendered → validated → accepted`

Failed jobs enter `quarantined` with a review record.

Research models browse and produce cited briefs only. Blueprint models convert
approved briefs into locked schemas and quotas. Smaller models generate JSON or
Markdown files one job at a time. Independent solver models do not see the
proposed key. A stronger adjudicator sees both independent solutions and the
source material when they disagree.

No model may modify gold after seeing a failed score. Gold is generated from
the approved blueprint and observable source/response data, then frozen before
agent evaluation.

Every job records model/version, prompt hash, inputs, outputs, seed, retry
count, token/cost usage, reviewer decisions, and artifact hashes. Re-running
the same job is idempotent.

## 8. Data layout and task IDs

```text
data/
  sources/
    source-ledger.jsonl
    briefs/companies/
    briefs/courses/
  banking/
    sec/raw/
    sec/normalized/
    reports/specs/
    content/scenarios/
    content/gold/
    content/references/
  education/
    courses/
    assessments/
    gold/
    submissions/
    grading-worlds/
content_pipeline/
  schemas.py
  jobs.py
  provenance.py
  render.py
  validators.py
  sec.py
  banking.py
  research.py
  release.py
  cli.py
```

Stable IDs are:

- Banking: `CB-PUB-{TICKER}-{AR|NM|AW|WL}-{BASE|REC|ADV}`
- Education: `TA-{COURSE}-{PS1|PS2|QUIZ|MID|FINAL}-{version}`

Public manifests contain task prompts, source references, schemas, and
artifact hashes. Private gold is stored separately and only loaded by the
verifier/release tooling.

## 9. Release and validation gates

The first generated release manifest is `data/release-manifest.json`; the
`contentctl release manifest --root data` command recomputes it from the
validators and populates the counts below. The current generated snapshot is
structurally complete, but intentionally reports `benchmark_ready=false` until
independent solver/vision/originality review and repository fault-matrix repair
are complete:

| Artifact | Count |
|---|---:|
| SEC companies / selected filings / normalized facts | 20 / 100 / 1,040 |
| Banking scenarios / private gold / references | 240 / 240 / 80 |
| Courses / assessments / questions | 8 / 40 / 296 |
| Submission packages / grading worlds | 320 / 40 |

### SEC/banking

- 20 CIK/ticker mappings verified.
- 100 selected filings restorable offline.
- Every normalized fact traces to accession, concept, context, period, unit,
  and source hash.
- Derived metrics recompute exactly.
- Four report specifications and four renderers validate.
- 80 reference reports and 240 banking oracles pass.
- Wrong company, period, unit, filing, report type, unsupported number,
  authority bypass, and missing source citation each fail applicable criteria.

### Academic

- 40 assessments, 296 questions, 320 submission packages.
- Independent solver agreement on every released answer.
- No cross-split duplicates or score-predictive identifiers.
- Visible submissions match structured responses.
- Numeric, symbolic, code, equivalence, and tolerance tests pass.
- Public manifests contain no solution/gold.
- Every oracle passes and every applicable fault agent fails.

### Repository/release

- Clean install, Ruff, full pytest, oracle matrix, render checks, and offline
  restore pass.
- Release manifest reports generated/accepted/rejected/quarantined counts.
- Raw SEC archive is attached as `swivelbench-content-v1-sec-raw.tar.zst` with
  URL, SHA-256, and byte size committed.
- README and roadmap describe smoke tasks separately from V1 content.

## 10. Delivery order

1. Create and review this specification.
2. Implement schemas, provenance, job state, CLI, and renderers.
3. Run company/course research jobs and license review.
4. Acquire, hash, normalize, and package SEC data.
5. Implement four report specifications and type-driven verification.
6. Generate and verify 80 banking base cases plus 160 variants.
7. Create eight course blueprints and 40 assessment blueprints.
8. Generate and independently solve 296 questions.
9. Generate, render, and visually verify 320 submissions.
10. Build grading worlds, regrades, email instructions, and artifact exports.
11. Run all deterministic, originality, provenance, and adversarial gates.
12. Integrate accepted manifests into the registry and publish the V1 release.

## 11. Known limitations and prohibited claims

- A successful oracle run does not prove content realism.
- Synthetic lending overlays are not real credit decisions.
- SEC facts are public evidence, not investment advice or SEC endorsement.
- A model-generated question is not expert-validated until it passes the
  independent-solver and review gates.
- A visual submission is not a multimodal benchmark item unless the visible
  pixels contain the information used to determine its released score.
- V1 does not claim broad humanities grading or unrestricted essay judgement.
