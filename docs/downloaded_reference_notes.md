# Local academic reference notes

`downloaded_by_consti/` is a local-only reference corpus and is ignored by
Git. It must never be staged, committed, packaged, or uploaded. The generator
uses it for structural research only; it does not copy names, prompts,
solutions, grader comments, or answer wording.

The reference exports establish the following design requirements:

- Exam and homework questions use hierarchical subparts such as `1.1`, `1.2`,
  and `2.1`, rather than a flat list of one-line prompts.
- Questions combine computation, interpretation, derivation, diagrams or
  algorithm reasoning, and explicit justification.
- Rubrics use question-level point totals plus granular criteria for correct,
  blank, incorrect, incomplete, or partially justified work.
- Grader exports record criterion flags, numeric scores, comments, grader
  identity, and adjustment state.
- Student work is an image/PDF artifact; the answer cannot be inferred from a
  filename or hidden identifier.

These observations are implemented as original SwivelBench content in the
versioned schemas and renderers under `content_pipeline/`.
