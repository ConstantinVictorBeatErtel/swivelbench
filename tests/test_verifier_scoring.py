"""Phase 1 minor-cleanup acceptance tests (core/verifier.py):

  - weight= actually shapes criterion_pass_rate instead of being parsed and
    ignored.
  - a malformed assertion (bad SQL) is excluded from the scored denominator
    and surfaced via Result.errors, rather than silently counting as a miss
    against the agent.
  - role_aware_reward is wired into the Verifiers adapter as an optional
    reward, not dead code.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402


def _dbs(tmp: Path) -> tuple[Path, Path]:
    a, b = tmp / "a.db", tmp / "b.db"
    for path in (a, b):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE marker (value INTEGER)")
        con.execute("INSERT INTO marker VALUES (1)")
        con.commit()
        con.close()
    return a, b


def test_weight_shapes_criterion_pass_rate():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = _dbs(root)
        assertions = root / "assertions.sql"
        assertions.write_text(
            """\
-- @assert id=HEAVY_MISS kind=positive weight=3.0 step=S1 level=tool role=required
SELECT 0;
-- @assert id=LIGHT_HIT kind=positive weight=1.0 step=S1 level=tool role=required
SELECT 1;
"""
        )
        result = verifier.verify(a, b, assertions)
        # Unweighted would be 0.5 (1 of 2 criteria); weighted is 1/(3+1).
        assert result.criterion_pass_rate == 0.25
        assert result.task_passed is False


def test_malformed_assertion_excluded_from_denominator_and_errors_loudly():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = _dbs(root)
        assertions = root / "assertions.sql"
        assertions.write_text(
            """\
-- @assert id=OK kind=positive weight=1.0 step=S1 level=tool role=required
SELECT 1;
-- @assert id=BROKEN kind=positive weight=1.0 step=S1 level=tool role=required
SELECT * FROM no_such_table;
"""
        )
        result = verifier.verify(a, b, assertions)
        # BROKEN must not count in the denominator: 1/1, not 1/2.
        assert result.criteria_total == 1
        assert result.criterion_pass_rate == 1.0
        assert result.task_passed is True
        # But the rubric bug must still be loudly visible.
        assert "BROKEN" in result.errors
        assert "BROKEN" not in result.passed
        assert "BROKEN" not in result.failed


def test_role_aware_reward_is_wired_into_verifiers_adapter():
    import inspect

    from adapters.verifiers import load_environment
    sig = inspect.signature(load_environment)
    assert "role_aware_alpha" in sig.parameters
    assert "role_aware_beta" in sig.parameters


def test_role_aware_reward_matches_spec():
    outcomes = [
        verifier.CriterionOutcome(id="r1", kind="positive", step="S1",
                                  level="ground", role="required", passed=True),
        verifier.CriterionOutcome(id="r2", kind="positive", step="S1",
                                  level="ground", role="required", passed=False),
        verifier.CriterionOutcome(id="b1", kind="positive", step="S1",
                                  level="ground", role="bonus", passed=True),
        verifier.CriterionOutcome(id="p1", kind="negative", step="S1",
                                  level="ground", role="penalty", passed=False),
    ]
    result = verifier.Result(
        criterion_pass_rate=0.0, task_passed=False, passed=[], failed=[],
        criteria=outcomes)
    # required rate = 0.5, + alpha*bonus_rate(1.0) - beta*unmet_penalty(1.0)
    reward = verifier.role_aware_reward(result, alpha=0.2, beta=0.5)
    assert reward == round(max(0.0, min(1.0, 0.5 + 0.2 * 1.0 - 0.5 * 1.0)), 4)
