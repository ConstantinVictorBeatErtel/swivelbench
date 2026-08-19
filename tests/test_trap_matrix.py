"""Phase 5 acceptance tests: test the model against the traps, not just the
verifier against the oracle.

Before this phase, the only environment-side randomness in grading was one
submission-kind rng.choice; every adversarial gate ran against the single
frozen GR-SEED-001 world. §0.1 of the hardening plan calls this out
explicitly: it answers "does the rubric catch a bad agent" (a
rubric-blindness gate), not "is the model actually exercised against the
traps." This file adds the two-sided matrix the plan asks for:

  test_rubric_blindness   — AGENT_FAULTS x sampled worlds: every fault must
                             fail task_passed on every world, not just the
                             seed.
  test_world_soundness    — ~50 sampled scenarios: the policy oracle scores
                             exactly 1.000, and an idle agent scores 0.000.
  test_trap_coverage      — every WORLD_AXES trap: at least one criterion is
                             tagged with it, and the oracle/idle contrast
                             actually flips that criterion's outcome.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, verifier  # noqa: E402
from envs.grading import oracle as gr_oracle  # noqa: E402
from envs.grading.runtime import make_api  # noqa: E402
from envs.grading.scenario import WORLD_AXES, make_scenario  # noqa: E402
from envs.grading.steps import run_through  # noqa: E402
from envs.grading.task import SEED_TASK  # noqa: E402


class Drop:
    """Wrap an ActionAPI so calls to `drop` names silently no-op — used to
    simulate an agent that skips a required action (e.g. never logs)."""

    def __init__(self, api, *drop: str) -> None:
        self._api, self._drop = api, set(drop)

    def __getattr__(self, name: str):
        if name in self._drop:
            return lambda *a, **k: {"ok": True, "suppressed": True}
        return getattr(self._api, name)


GR_FAULTS = [
    ("gr_no_trail", lambda api: run_through(Drop(api, "log_action")), None),
    ("gr_messy_email", run_through, {"use_messy_email": True}),
    ("gr_wrong_student", run_through, {"wrong_student": True}),
    ("gr_skip_regrades", run_through, {"skip_regrades": True}),
    ("gr_grant_bait", run_through, {"grant_bait": True}),
    ("gr_full_unclear", run_through, {"full_credit_unclear": True}),
]

SAMPLE_SEEDS = list(range(65001, 65016))  # 15 sampled worlds


def _build_and_score(seed: int, build, flags: dict | None):
    sc = make_scenario(seed=seed, split="train", difficulty=3)
    work = Path(tempfile.mkdtemp(prefix="sb_trapmatrix_"))
    try:
        from envs.grading.scenario import emit_fixture_files
        fixtures = work / "fixtures"
        emit_fixture_files(sc, fixtures)
        pa, pb = db.build(work, fixtures=fixtures, name_a="inbox.db",
                          name_b="gradescope.db", seed_a="seed_a.sql",
                          seed_b="seed_b.sql")
        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work / "artifacts")
        gr_oracle.FLAGS.clear()
        gr_oracle.FLAGS.update(flags or {})
        try:
            build(api)
        finally:
            gr_oracle.FLAGS.clear()
        api.close()
        return sc, verifier.verify(pa, pb, fixtures / "assertions.sql",
                                   domain="grading",
                                   artifacts_dir=work / "artifacts")
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.parametrize("seed", SAMPLE_SEEDS)
@pytest.mark.parametrize("name,build,flags", GR_FAULTS, ids=[f[0] for f in GR_FAULTS])
def test_rubric_blindness(name, build, flags, seed):
    """Every AGENT_FAULT must fail task_passed on every sampled world, not
    just the frozen seed — a rubric-blindness gate that actually spans the
    axis space instead of asking the same one question 15 times."""
    sc, res = _build_and_score(seed, build, flags)
    assert not res.task_passed, (
        f"{name} on seed {seed} (axes={sc.axes}) achieved task_passed; "
        f"reward is blind. failed={res.failed}")


@pytest.mark.parametrize("seed", range(66001, 66051))  # 50 scenarios
def test_world_soundness(seed):
    """The policy oracle must score exactly 1.000 on every sampled world,
    and an idle agent exactly 0.000 — the two floors the whole benchmark's
    reward signal rests on."""
    sc = make_scenario(seed=seed, split="train", difficulty=3)
    work = Path(tempfile.mkdtemp(prefix="sb_soundness_"))
    try:
        from envs.grading.scenario import emit_fixture_files
        fixtures = work / "fixtures"
        emit_fixture_files(sc, fixtures)
        pa, pb = db.build(work, fixtures=fixtures, name_a="inbox.db",
                          name_b="gradescope.db", seed_a="seed_a.sql",
                          seed_b="seed_b.sql")

        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work / "artifacts")
        run_through(api)
        api.close()
        res = verifier.verify(pa, pb, fixtures / "assertions.sql",
                              domain="grading", artifacts_dir=work / "artifacts")
        assert res.task_passed, (seed, sc.axes, res.failed, res.errors)
        assert res.criterion_pass_rate == 1.0, (seed, sc.axes, res.failed)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    work2 = Path(tempfile.mkdtemp(prefix="sb_soundness_idle_"))
    try:
        from envs.grading.scenario import emit_fixture_files
        fixtures = work2 / "fixtures"
        emit_fixture_files(sc, fixtures)
        pa, pb = db.build(work2, fixtures=fixtures, name_a="inbox.db",
                          name_b="gradescope.db", seed_a="seed_a.sql",
                          seed_b="seed_b.sql")
        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work2 / "artifacts")
        api.close()  # idle: no tool calls at all
        res = verifier.verify(pa, pb, fixtures / "assertions.sql",
                              domain="grading", artifacts_dir=work2 / "artifacts")
        assert res.criterion_pass_rate == 0.0, (seed, sc.axes, res.passed)
    finally:
        shutil.rmtree(work2, ignore_errors=True)


ALL_TRAPS = sorted({t for values in WORLD_AXES.values() for _, t in values if t})


@pytest.mark.parametrize("trap", ALL_TRAPS)
def test_trap_coverage(trap):
    """Every trap defined in WORLD_AXES must have at least one criterion
    tagged with it in some scenario, and that criterion must actually flip:
    pass when the oracle handles the trap correctly, fail when an idle
    agent does nothing about it. An untagged or unreachable trap here means
    the axis library grew a fault mode with no criterion actually watching
    it."""
    from envs.grading.criteria import build_criteria

    seed = None
    sc = None
    for candidate_seed in range(67001, 67201):
        candidate = make_scenario(seed=candidate_seed, split="train", difficulty=3)
        if trap in candidate.gold["traps"]:
            tagged = [c for c in build_criteria(candidate) if c.trap == trap]
            if tagged:
                seed, sc = candidate_seed, candidate
                break
    assert sc is not None, f"trap {trap!r} never reachable/tagged in 200 samples"

    tagged_ids = {c.id for c in build_criteria(sc) if c.trap == trap}
    assert tagged_ids, f"trap {trap!r}: no tagged criterion in seed {seed}"

    from envs.grading.scenario import emit_fixture_files

    # Oracle side: the trap-tagged criteria must pass.
    work = Path(tempfile.mkdtemp(prefix="sb_trapcov_oracle_"))
    try:
        fixtures = work / "fixtures"
        emit_fixture_files(sc, fixtures)
        pa, pb = db.build(work, fixtures=fixtures, name_a="inbox.db",
                          name_b="gradescope.db", seed_a="seed_a.sql",
                          seed_b="seed_b.sql")
        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work / "artifacts")
        run_through(api)
        api.close()
        res = verifier.verify(pa, pb, fixtures / "assertions.sql",
                              domain="grading", artifacts_dir=work / "artifacts",
                              with_details=True)
        oracle_pass = {c.id: c.passed for c in res.criteria if c.id in tagged_ids}
    finally:
        shutil.rmtree(work, ignore_errors=True)

    assert oracle_pass and all(oracle_pass.values()), (
        f"trap {trap!r}: oracle did not pass its own tagged criteria: "
        f"{oracle_pass}")

    # Idle side: the same trap-tagged criteria must fail.
    work2 = Path(tempfile.mkdtemp(prefix="sb_trapcov_idle_"))
    try:
        fixtures = work2 / "fixtures"
        emit_fixture_files(sc, fixtures)
        pa, pb = db.build(work2, fixtures=fixtures, name_a="inbox.db",
                          name_b="gradescope.db", seed_a="seed_a.sql",
                          seed_b="seed_b.sql")
        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work2 / "artifacts")
        api.close()
        res2 = verifier.verify(pa, pb, fixtures / "assertions.sql",
                               domain="grading", artifacts_dir=work2 / "artifacts",
                               with_details=True)
        idle_pass = {c.id: c.passed for c in res2.criteria if c.id in tagged_ids}
    finally:
        shutil.rmtree(work2, ignore_errors=True)

    assert idle_pass and not any(idle_pass.values()), (
        f"trap {trap!r}: idle agent still passed a tagged criterion "
        f"(vacuous check): {idle_pass}")
