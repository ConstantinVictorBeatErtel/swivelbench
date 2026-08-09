"""Regression tests for strict published grading and result metadata."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from core import verifier
from envs.commercial_banking.runtime import make_api as cb_make_api
from envs.commercial_banking.runtime import prepare as cb_prepare
from envs.commercial_banking.steps import run_one_request
from envs.commercial_banking.task import E2E_TASKS
from envs.grading.runtime import prepare as gr_prepare
from envs.grading.task import E2E_TASKS as GR_E2E_TASKS
from viz.server import _score_story


def _dbs(tmp: Path) -> tuple[Path, Path]:
    a, b = tmp / "a.db", tmp / "b.db"
    for path in (a, b):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE marker (value INTEGER)")
        con.execute("INSERT INTO marker VALUES (1)")
        con.commit()
        con.close()
    return a, b


def test_one_missed_criterion_is_not_a_pass() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = _dbs(root)
        assertions = root / "assertions.sql"
        assertions.write_text(
            """\
-- @assert id=OK kind=positive step=S1 level=tool role=required
SELECT 1;
-- @assert id=MISS kind=positive step=S1 level=tool role=required
SELECT 0;
"""
        )
        result = verifier.verify(a, b, assertions)
        assert result.criterion_pass_rate == 0.5
        assert result.criteria_passed == 1
        assert result.criteria_total == 2
        assert result.task_passed is False


def test_empty_rubric_is_not_a_pass() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = _dbs(root)
        assertions = root / "assertions.sql"
        assertions.write_text("-- no active criteria\n")
        result = verifier.verify(a, b, assertions)
        assert result.criterion_pass_rate == 1.0
        assert result.criteria_total == 0
        assert result.task_passed is False


def test_story_never_promotes_partial_rate_to_pass() -> None:
    story = _score_story(0.9999, False, [])
    assert "task_passed=false" in story
    assert "every rubric criterion" not in story


def test_generated_assertions_have_strict_metadata() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cb_work = root / "cb"
        cb_work.mkdir()
        _, _, cb_assertions = cb_prepare(E2E_TASKS["CB-L1-001"], cb_work)
        cb_loaded = verifier.load(cb_assertions)
        assert cb_loaded
        assert all(a.step and a.level and a.role for a in cb_loaded)

        gr_work = root / "gr"
        gr_work.mkdir()
        _, _, gr_assertions = gr_prepare(GR_E2E_TASKS["GR-L1-001"], gr_work)
        gr_loaded = verifier.load(gr_assertions)
        assert gr_loaded
        assert all(a.step and a.level and a.role for a in gr_loaded)


def test_multi_request_rollout_cannot_pass_from_one_request() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        task = E2E_TASKS["CB-L3-001"]
        pa, pb, assertions = cb_prepare(task, root)
        api = cb_make_api(pa, pb, task)
        first = api.list_credit_requests()["requests"][0]
        run_one_request(api, first)
        api.close()
        result = verifier.verify(
            pa, pb, assertions, domain="commercial_banking",
            artifacts_dir=root / "artifacts",
        )
        assert result.task_passed is False
