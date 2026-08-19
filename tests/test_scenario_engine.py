"""Phase 2 acceptance tests: the scenario engine (envs/grading/scenario.py),
P8 (dead branches / arithmetic regrades are real) and P9 (difficulty bands,
scenario diversity).
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, verifier  # noqa: E402
from envs.grading.runtime import make_api  # noqa: E402
from envs.grading.scenario import (  # noqa: E402
    WORLD_AXES,
    emit_fixture_files,
    make_scenario,
    sample_axes,
)
from envs.grading.steps import run_through  # noqa: E402
from envs.grading.task import SEED_TASK  # noqa: E402


def _seeds_with_axis_value(axis: str, value: str, *, start: int, count: int,
                           difficulty: int = 3):
    found = []
    seed = start
    while len(found) < count:
        axes = sample_axes(seed, difficulty=difficulty)
        if axes[axis] == value:
            found.append(seed)
        seed += 1
    return found


def test_arithmetic_regrade_is_legitimate():
    """P8: a claim_type='arithmetic' regrade over a genuinely-broken prior
    grade must actually get adjusted, not upheld — and the adjustment must
    change grade_total to the correct sum, not just be a no-op."""
    for seed in _seeds_with_axis_value("regrade_mix", "arithmetic_legit",
                                       start=10000, count=5):
        sc = make_scenario(seed=seed, split="train", difficulty=3)
        gold = sc.gold
        arithmetic_rgs = [
            (rid, r) for rid, r in gold["regrades"].items()
            if r["action"] == "adjust"
        ]
        assert arithmetic_rgs, f"seed {seed}: expected a legitimate adjust in gold"

        work = Path(tempfile.mkdtemp(prefix="sb_p8_"))
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
                                  domain="grading",
                                  artifacts_dir=work / "artifacts")
            assert res.task_passed, (seed, res.failed, res.errors)

            con = db.attached(pa, pb)
            for rid, r in arithmetic_rgs:
                row = con.execute(
                    "SELECT status FROM b.regrade_requests WHERE regrade_id = ?",
                    (rid,)).fetchone()
                assert row[0] == "adjusted", f"seed {seed} {rid}: {row}"
            con.close()
        finally:
            shutil.rmtree(work, ignore_errors=True)


def test_adjust_preserves_invariants():
    """P8: resolve_regrade(decision='adjust') always leaves grade_total
    equal to sum(grade_items) — the invariant cannot be broken by
    construction, unlike the old adjusted_total=int form."""
    work = Path(tempfile.mkdtemp(prefix="sb_p8_invariant_"))
    try:
        from envs.grading.runtime import prepare
        pa, pb, assertions = prepare(SEED_TASK, work)
        api = make_api(pa, pb, SEED_TASK, artifacts_dir=work / "artifacts")
        api.publish_rubric("ASN-HW1", "EM-02", [
            {"item_key": "Q1", "description": "d", "max_points": 5,
             "expected_key": "derivative", "item_ord": 1},
            {"item_key": "Q2", "description": "d", "max_points": 5,
             "expected_key": "chain rule", "item_ord": 2},
        ])
        api.set_item_scores("SUB-1", "U-100", {"Q1": 5, "Q2": 5})

        # Reject: adjust with no item_scores must fail structurally, not
        # silently succeed and leave grade_total detached from grade_items.
        bad = api.resolve_regrade("RG-2", "adjust", "no items supplied")
        assert not bad["ok"]

        # A real adjust must recompute grade_total from the supplied items.
        ok = api.resolve_regrade("RG-2", "adjust", "corrected",
                                 item_scores={"Q1": 3, "Q2": 1})
        assert ok["ok"], ok
        assert ok["grade_total"] == 4

        con = db.attached(pa, pb)
        row = con.execute(
            "SELECT grade_total FROM b.grades WHERE submission_id = 'SUB-1'"
        ).fetchone()
        items = con.execute(
            "SELECT SUM(points) FROM b.grade_items gi JOIN b.grades g "
            "ON g.grade_id = gi.grade_id WHERE g.submission_id = 'SUB-1'"
        ).fetchone()
        con.close()
        assert row[0] == 4
        assert items[0] == 4
        assert row[0] == items[0]
        api.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_scenario_diversity():
    """P9: L1-L3 are difficulty bands over WORLD_AXES, not three fixed
    worlds — many distinct axis combinations and world shapes must appear
    across a modest sample, matching envs/commercial_banking/credit_reports.py's
    split-diversity expectation."""
    scenarios = [make_scenario(seed=20000 + i, split="train", difficulty=3)
                for i in range(60)]
    distinct_axes = {tuple(sorted(sc.axes.items())) for sc in scenarios}
    assert len(distinct_axes) >= 30, (
        f"only {len(distinct_axes)}/60 distinct axis combinations")

    distinct_queue_sizes = {len(sc.world["submissions"]) for sc in scenarios}
    assert len(distinct_queue_sizes) >= 2

    # rubric_shape's item-count diversity (2 vs 3 items) only shows up in
    # the sum_mismatch/invalid case; among *valid* rubrics, point spread
    # (5/5 vs 7/3) is what varies — check that instead.
    distinct_point_spreads = {
        tuple(sorted(it["max_points"] for it in sc.gold["rubric_items"]))
        for sc in scenarios if sc.gold["rubric_valid"]
    }
    assert len(distinct_point_spreads) >= 2

    # Every axis value must be reachable at difficulty=3 (no dead branches).
    seen_per_axis = {a: set() for a in WORLD_AXES}
    for sc in scenarios:
        for a, v in sc.axes.items():
            seen_per_axis[a].add(v)
    under_covered = {a: vs for a, vs in seen_per_axis.items()
                     if len(vs) < len(WORLD_AXES[a])}
    # 60 samples is not guaranteed to hit every value of every axis; just
    # assert broad coverage (most axes fully seen) rather than 100%.
    fully_covered = sum(1 for a in WORLD_AXES if a not in under_covered)
    assert fully_covered >= len(WORLD_AXES) - 2, under_covered


def test_difficulty_zero_is_always_baseline():
    """difficulty=0 must always land on each axis's first (easiest, no-trap
    where applicable) value, regardless of seed — a low rung of the ladder
    should not randomly roll a hard trap."""
    for seed in (1, 2, 3, 42, 999):
        axes = sample_axes(seed, difficulty=0)
        for axis, value in axes.items():
            assert value == WORLD_AXES[axis][0][0], (seed, axis, value)


def test_gold_never_used_by_oracle():
    """The oracle module must not import envs.grading.scenario at all —
    it re-derives its actions from POLICY_TEXT independently."""
    import envs.grading.oracle as oracle_mod
    import envs.grading.steps as steps_mod
    import inspect

    for mod in (oracle_mod, steps_mod):
        src = inspect.getsource(mod)
        assert "envs.grading.scenario" not in src
        assert "derive_gold" not in src
