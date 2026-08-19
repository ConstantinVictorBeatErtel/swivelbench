"""Phase 3 acceptance tests: envs/grading/criteria.py's CRITERION_TEMPLATES
registry (P10) — gold-derived metadata/trap attribution, and the
anti-memorization structural gate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.grading.criteria import build_criteria  # noqa: E402
from envs.grading.scenario import WORLD_AXES, make_scenario  # noqa: E402
from envs.grading.task import E2E_TASKS, SEED_TASK  # noqa: E402

# Schema-level vocabulary (status enums, action codes, claim types) — these
# are part of the DB/tool contract, not scenario-specific identity data, so
# they're legitimately hardcoded across every scenario rather than sourced
# from gold.
SCHEMA_VOCAB = {
    "open", "upheld", "adjusted",
    "out_of_rubric", "arithmetic", "clarity_partial",
    "publish_rubric", "open_submissions", "grade_item", "resolve_regrade",
    "note",
}

STRING_LITERAL_RE = re.compile(r"'((?:[^']|'')*)'")


def _string_literals(sql: str) -> set[str]:
    return {m.replace("''", "'") for m in STRING_LITERAL_RE.findall(sql)}


def test_no_unbound_literals():
    """Every non-schema-vocabulary string literal in a generated criterion's
    SQL must appear somewhere in that scenario's gold manifest — the class
    of bug this catches: an assertion hardcoding 'EM-02'/'SUB-1'/'U-101'
    that the sampled world no longer guarantees.

    Runs over many sampled scenarios (not just the seed task) so it keeps
    catching this as WORLD_AXES grows, per the plan's own instruction that
    this gate must not be a one-off check.
    """
    offenders = []
    for seed in range(30001, 30061):
        sc = make_scenario(seed=seed, split="train", difficulty=3)
        gold_blob = json.dumps(sc.gold, default=str)
        for c in build_criteria(sc):
            for lit in _string_literals(c.sql):
                if lit in SCHEMA_VOCAB:
                    continue
                if lit not in gold_blob:
                    offenders.append((sc.scenario_id, c.id, lit))
    assert not offenders, offenders[:20]


def test_criterion_metadata_comes_from_template_not_id_suffix():
    """P10: level/role come from the template that emitted the criterion,
    not an id-suffix lookup — regression guard for the old
    envs/grading/seeder.py::_annotate_generated regex approach, which put
    every S3 criterion at level=ground and skipped L3_adaptability
    entirely for generated tasks."""
    sc = make_scenario(seed=40001, split="train", difficulty=3)
    criteria = build_criteria(sc)
    levels = {c.level for c in criteria}
    # A scenario touching escalation/regrade paths should span more than
    # just "ground" — plan/adapt/reason/tool should also appear.
    assert len(levels) >= 3, levels
    for c in criteria:
        assert c.step in ("S1_rubric", "S2_queue", "S3_grade", "S4_regrades")
        assert c.level in verifier.LEVELS
        assert c.role in verifier.ROLES


def test_by_trap_attributes_failures():
    """A criterion tagged trap=X must actually flip when the world's X
    trap is exercised vs. its baseline — attribution has to be real, not
    just present."""
    # Find a seed where identity_noise lands on collision_twin at max
    # difficulty, and confirm the resulting criteria carry that trap and
    # that trap coverage is reachable (Phase 5 builds the full sweep; this
    # is a direct existence check that the plumbing works end to end).
    found_traps = set()
    for seed in range(50001, 50101):
        sc = make_scenario(seed=seed, split="train", difficulty=3)
        for c in build_criteria(sc):
            if c.trap:
                found_traps.add(c.trap)
    all_traps = {t for values in WORLD_AXES.values() for _, t in values if t}
    missing = all_traps - found_traps
    assert not missing, f"traps never attributed to any criterion: {missing}"


def test_trap_metadata_round_trips_through_verifier_load(tmp_path):
    """core/verifier.py's load() must parse trap= and Result must expose
    by_trap — the metadata grammar addition this phase requires."""
    assertions = tmp_path / "assertions.sql"
    assertions.write_text(
        """\
-- @assert id=A kind=positive weight=1.0 step=S1 level=tool role=required trap=my_trap
SELECT 1;
-- @assert id=B kind=positive weight=1.0 step=S1 level=tool role=required
SELECT 0;
"""
    )
    loaded = verifier.load(assertions)
    by_id = {a.id: a for a in loaded}
    assert by_id["A"].trap == "my_trap"
    assert by_id["B"].trap == ""


def test_generated_tasks_still_load_with_trap_grammar():
    """Generated E2E task assertions (built through the new criteria.py
    path) must still parse cleanly under core/verifier.py's grammar."""
    for task_id, task in E2E_TASKS.items():
        if task.use_bundled_fixtures:
            continue
        import shutil
        import tempfile
        from envs.grading.runtime import prepare

        work = Path(tempfile.mkdtemp(prefix="sb_trap_load_"))
        try:
            _, _, assertions = prepare(task, work)
            loaded = verifier.load(assertions)
            assert loaded, task_id
            assert all(a.step and a.level and a.role for a in loaded)
        finally:
            shutil.rmtree(work, ignore_errors=True)


def test_seed_task_unaffected_by_trap_grammar():
    """GR-SEED-001's bundled assertions.sql predates trap= and must still
    load fine with trap defaulting to ''."""
    loaded = verifier.load(SEED_TASK.assertions)
    assert loaded
    assert all(a.trap == "" for a in loaded)
