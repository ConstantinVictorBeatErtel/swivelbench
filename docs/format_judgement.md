# File format judgement

SwivelBench agents leave real Excel (`.xlsx`) and Word (`.docx`) files on disk.
Database SQL assertions still decide most of the reward. **Format checks**
(`kind=format`, 10% of the score) ask a separate question: did the agent
actually produce a correctly structured Office file?

There is **no LLM judge in the default scorer**. Structural checks unzip the
OOXML and look for required sheets, headings, and fields. An optional LLM
rubric is included below for research / human review only.

## Agent prompt contract

Add (or keep) this language in the task prompt / policy so the model knows
what “formatted” means:

### Commercial banking

```
Deliverables (file formatting — graded)
  - After write_model_cells, leave a real .xlsx under artifacts/excel/.
    It must have a sheet named Model, a Field/Value header row, and one
    labeled row each for: revenue, ebitda, total_debt, interest_expense,
    leverage.
  - After writing report sections, leave a real .docx credit memo under
    artifacts/reports/. Section headings must be exactly the chosen
    template's required_sections, in order, each with a non-empty body.
  - Choosing a report template is itself a format decision: never select a
    corrupted template (corrupt = 1).
```

### Grading

```
Deliverables (file formatting — graded)
  - After set_item_scores, leave a real .docx gradesheet under
    artifacts/reports/gradescope_gradesheet.docx titled
    "Gradescope Gradesheet".
  - Each graded submission must appear as a heading with item lines and a
    Total: line.
```

## Deterministic judgement criteria (scored)

| ID | Domain | Pass when | Fail when |
|---|---|---|---|
| **F1** | CB | Valid `.xlsx` OOXML; sheet `Model`; `Field`/`Value` header; rows for revenue, ebitda, total_debt, interest_expense, leverage | Missing file, corrupt zip, wrong sheet, missing fields |
| **F2** | CB | Valid `.docx` OOXML; headings Executive Summary → Financial Analysis → Covenant Review → Recommendation in order; each has non-empty body | Missing file, missing/out-of-order heading, empty section |
| **F1** | GR | Valid `.docx` OOXML; title contains `Gradescope Gradesheet`; ≥3 `Total:` lines | Missing file, wrong title, too few totals |

Implementation: `core/format_check.py`, merged into `core/verifier.verify(..., domain=..., artifacts_dir=...)`.

Outcome language for the UI:

- **Passed** — file exists and matches the structural contract above.
- **Missed** — no file, invalid OOXML, or required labels/headings absent.
  Detail string from the checker explains which rule failed.

## Optional LLM formatting rubric (not in default score)

Use only when you want prose/layout quality beyond structure. **Do not** fold
into `criterion_pass_rate` / `task_passed` until the criterion passes the
adversarial calibration loop in `eval/calibrate_criterion.py`
(ComplexConstraints §3.3: draft → hand-grade → judge agree → flip-test).

Score LLM criteria separately; mark `calibrated=true` before enabling.

**Judge prompt (CB memo):**

> You are grading a credit-memo `.docx` for formatting quality only, not credit
> correctness. Given the document text, score 0.0–1.0.
>
> Criteria (equal weight):
> 1. Headings match the required four titles and appear in order.
> 2. Each section body is substantive (≥2 sentences), not placeholder.
> 3. Numbers cited in Financial Analysis are internally consistent with each other.
> 4. No empty headings; no obvious template garbage or duplicated blocks.
>
> Return JSON: `{"score": <float>, "passed": <bool>, "rationale": "<≤80 words>"}`.
> `passed` is true iff score ≥ 0.75.

**Judge prompt (GR gradesheet):**

> You are grading a Gradescope gradesheet `.docx` for formatting quality only.
> Score 0.0–1.0.
>
> Criteria:
> 1. Title identifies the sheet as Gradescope grades.
> 2. Every submission has a clear heading, itemized scores, and a Total.
> 3. Totals equal the sum of listed item points when arithmetic is checkable.
> 4. Layout is scannable (no collapsed blob of scores without labels).
>
> Return the same JSON schema as above; `passed` iff score ≥ 0.75.

**Judge prompt (CB Excel):**

> You are grading a financial-model `.xlsx` export for formatting quality only.
> Score 0.0–1.0.
>
> Criteria:
> 1. One clear model sheet with Field/Value columns.
> 2. Required field labels present and spelled correctly.
> 3. Numeric cells are numbers (not text junk) for the five financial fields.
> 4. Digest / source id is present when the run claims a digest.
>
> Return the same JSON schema; `passed` iff score ≥ 0.8.

## Reward share

Every active criterion (SQL + format) contributes equally to
`criterion_pass_rate`. `task_passed` requires all of them. Kind labels
(positive / propagation / negative / trail / format) remain for diagnostics
only — they no longer reweight the score.
