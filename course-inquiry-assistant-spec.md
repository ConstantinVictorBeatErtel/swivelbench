# Course & Program Inquiry Assistant — Product Spec

**Status:** Draft v0.1
**Owner:** Constantin Ertel
**Sponsor:** Prof. Kerger (IEOR, UC Berkeley)
**Date:** August 2026

---

## 1. Problem

Faculty and program staff spend a large, recurring share of their time answering
student inquiries that are already answered in writing somewhere — in the
syllabus, the program handbook, the course catalog, or 12twenty. The same
questions recur every semester, arrive over email and Ed, and require the
responder to know which of several systems holds the current answer.

The cost is not intellectual. It is lookup and transcription.

## 2. Goal

A system that answers routine student inquiries accurately, cites its source,
and refuses when it does not know — evaluated rigorously enough that a
department can decide whether to deploy it.

The deliverable is **an evaluated system plus the evaluation itself**. The
evaluation set is the durable asset: it stays useful regardless of which model,
vendor, or architecture is eventually chosen.

## 3. Non-goals (v1)

- No student-facing deployment. No UI beyond a minimal demo interface.
- No integration with live 12twenty, Gradescope, bCourses, or SIS.
- No use of student-authored or grade data (see §4).
- No write actions of any kind. Read and answer only.
- No multi-course generalization. One program, one semester of documents.

Actions across systems are Phase 2 and are specified separately (§10).

## 4. Data policy — read this before collecting anything

Student posts on Ed, and everything in Gradescope, are **education records under
FERPA**. Prior enrollment does not confer the right to repurpose them. This
constraint is not a footnote; it determines the architecture, and it is the
strongest argument for on-premises inference.

### Tier 1 — Use without permission
Syllabus, course website, program handbook, degree requirement pages, course
catalog, public department FAQ, public 12twenty help documentation.
**This is sufficient to build v1.**

### Tier 2 — Requires Kerger's export and explicit sign-off
De-identified Ed question archive (question text only; no author, no
identifiers, no thread metadata tying posts to individuals). Used **only** to
validate the realism of the synthetic question distribution (§6.4). Not used as
training data in v1.

### Tier 3 — Excluded entirely
Gradescope submissions, grades, rosters, individual student emails, anything
identifiable. Not needed for this system. The exclusion is stated explicitly in
the writeup.

**Collection method:** native platform exports and APIs. No screen recording, no
scraping of authenticated views.

## 5. Corpus

| Source | Est. size | Volatility | Notes |
|---|---|---|---|
| Course syllabi | ~5K tokens each | Per semester | Primary source for course-level questions |
| Program handbook | ~30–60K tokens | Annual | Degree requirements, policies |
| Course catalog / schedule | ~20K tokens | Per semester | Prereqs, offerings |
| Career services / 12twenty docs | ~10–20K tokens | Rolling | Reporting requirements, posting rules |
| Department FAQ / web pages | ~10K tokens | Rolling | |

**Total: roughly 80–150K tokens.** Small. This fact drives the architecture
decision in §7.

Every document is versioned on ingest with a `valid_from` / `valid_until` date.
Time-sensitive questions cannot be evaluated without this.

## 6. Question sourcing pipeline

Four stages, deliberately ordered so that human judgment anchors everything
downstream.

### 6.1 Human-sourced seed set — **owner: Constantin**

Write out, from memory and from the documents, the questions students actually
ask. Target: **60–80 questions**, each with:

- question text
- verified answer
- source document + section
- category (§6.5)
- date the answer was verified

**These answers are hand-verified against the source. No exceptions.** This set
is the evaluation set. A generated eval set with generated answers measures only
agreement between two models.

Budget: ~4–6 hours. This is the single highest-value block of work in the
project.

### 6.2 Model-assisted sourcing — **owner: model, reviewed by Constantin**

The model reads each document and proposes questions the document answers,
plus questions it *appears* to answer but does not. Purpose: surface blind
spots in the human seed set — question types that didn't occur to you.

Output goes into a review queue. Constantin accepts, edits, or rejects each.
Accepted items get hand-verified answers and join the eval set. **Nothing enters
the eval set unreviewed.**

Target: +20–40 accepted questions.

### 6.3 Synthetic expansion — **owner: model**

Volume generation for *training* data only. Strictly separated from eval:
no document chunk that seeded an eval question may seed a training question.

Generation axes:

- **Persona:** first-semester student, graduating student, international
  student, career-switcher. Different vocabulary and assumed knowledge.
- **Register:** clean and formal; terse and misspelled; unpunctuated mobile
  phrasing. Real inquiries are sloppy.
- **Scope:** single-chunk; cross-document (feed two chunks, require both);
  temporal (answer differs by semester).
- **Negatives:** plausible questions the corpus cannot answer. Ground truth is a
  refusal plus a pointer to a human.

Target: 3–5K question/answer pairs.

Reference recipe: **self-study** from the Cartridges paper — generate synthetic
conversations about the corpus, train with a context-distillation objective.
Implementation available at `github.com/HazyResearch/cartridges`
(`examples/arxiv/arxiv_synthesize.py`).

### 6.4 Distribution validation

Once the Tier 2 Ed export is available: sample ~30 real questions, categorize
them against the taxonomy, and compare the distribution to the synthetic set.

**A mismatch is a result, not a failure.** If synthetic questions skew
single-source factual while real ones skew multi-source and procedural, that
gap is one of the more interesting things in the writeup.

### 6.5 Category taxonomy

| Category | Definition | Why it matters |
|---|---|---|
| `single_source` | Answer in one document section | Baseline competence |
| `multi_source` | Requires ≥2 documents | Where retrieval is expected to fail |
| `temporal` | Answer depends on term/year | Tests versioning |
| `procedural` | "How do I..." multi-step | Common in practice, hard to score |
| `unanswerable` | Not in corpus | **Most important category** |

Report metrics per category. A single aggregate number hides the only
differences that matter.

## 7. System arms

Three arms, same eval set, same corpus.

### Arm A — Retrieval baseline (RAG) — **primary system**

Chunk, embed, retrieve top-k, answer with citations. Standard.

This is the system intended for deployment. Rationale:

- **Citations are non-negotiable** in an advising context. Students must be able
  to verify; the department needs a record of what was asserted.
- **Corpus is ~100K tokens** — small enough that prompt caching already
  amortizes prefill across queries.
- **Update cost is near zero.** Re-index one document when a deadline changes.

### Arm B — Trained memory (cartridge)

Train a KV cache offline on the static subset of the corpus via self-study;
load at inference.

Run as a **controlled comparison with a stated hypothesis**, not as the
intended deployment. Hypothesis:

> Cartridges will underperform RAG on `single_source` and `temporal` questions,
> and may outperform on `multi_source`, with the gap widening as base model size
> decreases.

Reasoning: RAG fails when an answer requires chunks that do not co-retrieve.
A cartridge sees the full corpus at training time. Separately, a 4B-class model
reasons poorly over 100K tokens of context, so the amortized-memory approach
should matter more at small scale — which is exactly the on-premises regime
FERPA pushes toward.

**If the hypothesis is wrong, say so.** A clean negative result — "the trained
memory approach does not pay off below corpus size X" — is a more useful finding
than a marginal positive one.

### Arm C — Hybrid

Cartridge over the stable core (handbook, degree requirements, policies —
annual churn); retrieval over the volatile layer (deadlines, postings, current
term data).

This is the architecturally interesting arm. It targets the known limitation
that cartridges are monolithic and cannot be cheaply partially retrained.

**Build A first. B and C only if A ships and time remains.**

## 8. Metrics

Per category, per arm:

- **Accuracy** — answer matches verified ground truth. Human-graded on the eval
  set; model-graded scoring reported separately and never as the headline
  number.
- **Citation validity** — cited source actually contains the answer. Arm A only.
- **Refusal rate on `unanswerable`** — target: high. A confidently wrong answer
  about a degree requirement or a filing deadline is the failure mode that kills
  deployment.
- **False refusal rate on answerable questions** — the counterweight; a system
  that refuses everything scores perfectly on the metric above.
- **Cost per query** — tokens in/out, and amortized training cost for Arms B/C
  divided over projected semester query volume.
- **Update latency** — wall-clock time to correct a changed deadline end to end.

Report at two model scales: a frontier API model and a 4B-class local model.
The scale comparison is where the on-premises argument is made or lost.

## 9. Phases

| Phase | Work | Est. effort | Gate |
|---|---|---|---|
| 0 | Collect Tier 1 corpus; version and date every document | 3 hrs | Corpus committed |
| 1 | Human seed eval set, 60–80 verified Q&A (§6.1) | 5 hrs | Eval set frozen |
| 2 | Model-assisted sourcing + review (§6.2) | 3 hrs | Eval set v1.0 |
| 3 | Arm A: RAG baseline + eval harness | 8 hrs | Per-category numbers |
| 4 | Memo + demo → **send to Kerger** | 3 hrs | **Ship here** |
| 5 | Synthetic expansion (§6.3) | 4 hrs | Training set built |
| 6 | Arm B: cartridge training + eval | 12 hrs | Hypothesis tested |
| 7 | Arm C: hybrid | 8 hrs | |
| 8 | Ed export → distribution validation (§6.4) | 3 hrs | Requires Kerger |

**Phase 4 is the ship gate.** Everything through Phase 4 is roughly two
weekends and does not require anything from Kerger except the initial
conversation. Phases 5–8 are the research extension and should only begin if
Phase 4 lands well.

## 10. Phase 2 (separate project) — actions across systems

Out of scope here. Recorded so the framing exists when it comes up.

The expensive administrative work is not answering questions; it is the
cross-system work: a student emails about a regrade, someone locates them in
Gradescope under a different key, applies the change, updates the gradebook,
and replies. Same entity across systems under different identifiers, a state
mutation, and an audit trail that must survive a grade dispute.

That is the swivel-chair problem in a course-operations domain, and it maps onto
the existing SwivelBench assertion structure:

- **positive** — the regrade applied
- **propagation** — the gradebook reflects it
- **audit trail** — who changed what, when
- **negative** — no other student's record moved

Propose only after Phase 4 succeeds.

## 11. Open questions

1. Will Kerger authorize a de-identified Ed export, and does it need IRB review
   if results are published?
2. Does the department have hardware for local inference, or is that
   hypothetical?
3. Which 12twenty content is public vs. authenticated? Determines corpus scope.
4. Is there an existing FAQ or canned-response document already in use? If so,
   it is both corpus and ground truth, and it moves Phase 1 considerably faster.
5. Who owns the answer when the handbook and 12twenty disagree? This is a policy
   question, not a technical one, and it will come up.

## 12. References

- Eyuboglu et al., *Cartridges: Lightweight and general-purpose long context
  representations via self-study* — arxiv.org/abs/2506.06266
- Implementation — github.com/HazyResearch/cartridges
- *Cartridges at Scale: Training Modular KV Caches over Large Document
  Collections* — arxiv.org/abs/2606.04557
- Diaz, *Learned structure in cartridges* — arxiv.org/abs/2508.17032
- Biderman et al., *LoRA Learns Less and Forgets Less* — arxiv.org/abs/2405.09673
