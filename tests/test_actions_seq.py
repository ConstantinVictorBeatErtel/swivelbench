"""P1 acceptance test: sequence counters must survive a fresh ActionAPI.

Step episodes build a DB by running an oracle prefix on one ActionAPI
instance, closing it, then handing the agent a fresh instance over the same
files (prepare_step_episode in both commercial_banking/steps.py and
envs/grading/steps.py). Before the fix, every counter (_audit_seq, _appr_seq,
_rubric_seq, _grade_seq, ...) restarted at 0 in the new instance and the next
INSERT collided with a PRIMARY KEY the prefix had already written.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from envs.commercial_banking.runtime import make_api as cb_make_api  # noqa: E402
from envs.commercial_banking.steps import STEP_ORDER as CB_STEPS  # noqa: E402
from envs.commercial_banking.steps import (  # noqa: E402
    prepare_step_episode as cb_prepare_step,
)
from envs.commercial_banking.task import SEED_TASK as CB_SEED  # noqa: E402
from envs.grading.runtime import make_api as gr_make_api  # noqa: E402
from envs.grading.steps import STEP_ORDER as GR_STEPS  # noqa: E402
from envs.grading.steps import prepare_step_episode as gr_prepare_step  # noqa: E402
from envs.grading.task import SEED_TASK as GR_SEED  # noqa: E402


def _assert_second_api_can_write(make_api, task, pa, pb) -> None:
    api2 = make_api(pa, pb, task)
    try:
        result = api2.log_action(
            "agent", api2.action_codes[0], api2.system_b_name,
            "SMOKE", "second API write")
        assert result["ok"], result
        approval = api2.request_approval("SMOKE", "no-op", "sequence smoke test")
        assert approval["ok"], approval
    finally:
        api2.close()


@pytest.mark.parametrize("step_id", CB_STEPS)
def test_second_api_over_same_db_can_write_cb(step_id):
    work = Path(tempfile.mkdtemp(prefix="sb_seq_cb_"))
    try:
        pa, pb, _ = cb_prepare_step(CB_SEED, step_id, work)
        _assert_second_api_can_write(cb_make_api, CB_SEED, pa, pb)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.parametrize("step_id", GR_STEPS)
def test_second_api_over_same_db_can_write_gr(step_id):
    work = Path(tempfile.mkdtemp(prefix="sb_seq_gr_"))
    try:
        pa, pb, _ = gr_prepare_step(GR_SEED, step_id, work)
        _assert_second_api_can_write(gr_make_api, GR_SEED, pa, pb)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_grading_third_api_over_grading_db_seeds_domain_counters():
    """A fresh API opened after the rubric+grading prefix has already run
    must also seed _rubric_seq/_grade_seq from existing rows, not just the
    base _audit_seq/_appr_seq counters."""
    work = Path(tempfile.mkdtemp(prefix="sb_seq_gr3_"))
    try:
        pa, pb, _ = gr_prepare_step(GR_SEED, "S4_regrades", work)
        api2 = gr_make_api(pa, pb, GR_SEED)
        try:
            result = api2.publish_rubric(
                "ASN-HW1", "EM-02",
                [{"item_key": "Q1", "description": "d", "max_points": 5,
                  "expected_key": "derivative", "item_ord": 1}])
            assert result["ok"], result
            grade = api2.set_item_scores("SUB-1", "U-100", {"Q1": 5})
            assert grade["ok"], grade
        finally:
            api2.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
