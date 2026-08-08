"""Track A step-episode smoke tests."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.commercial_banking.runtime import make_api as cb_make_api  # noqa: E402
from envs.commercial_banking.runtime import prepare as cb_prepare  # noqa: E402
from envs.commercial_banking.steps import STEP_ORDER, run_one_request  # noqa: E402
from envs.commercial_banking.task import SEED_TASK as CB_SEED  # noqa: E402
from envs.grading.runtime import make_api as gr_make_api  # noqa: E402
from envs.grading.runtime import prepare as gr_prepare  # noqa: E402
from envs.grading.steps import STEP_ORDER as GR_ORDER  # noqa: E402
from envs.grading.steps import run_through as gr_run_through  # noqa: E402
from envs.grading.task import SEED_TASK as GR_SEED  # noqa: E402


@pytest.mark.parametrize("step_id", STEP_ORDER)
def test_cb_step_oracle_passes_step_criteria(step_id):
    work = Path(tempfile.mkdtemp(prefix="sb_step_cb_"))
    try:
        pa, pb, assertions = cb_prepare(CB_SEED, work)
        api = cb_make_api(pa, pb, CB_SEED)
        run_one_request(api, api.list_credit_requests()["requests"][0],
                        through_step=step_id)
        api.close()
        res = verifier.verify(
            pa, pb, assertions, domain="commercial_banking",
            artifacts_dir=pa.parent / "artifacts", step=step_id)
        assert res.task_passed, (
            f"{step_id} failed={res.failed} rate={res.criterion_pass_rate}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.parametrize("step_id", GR_ORDER)
def test_gr_step_oracle_passes_step_criteria(step_id):
    work = Path(tempfile.mkdtemp(prefix="sb_step_gr_"))
    try:
        pa, pb, assertions = gr_prepare(GR_SEED, work)
        api = gr_make_api(pa, pb, GR_SEED)
        gr_run_through(api, through_step=step_id)
        api.close()
        res = verifier.verify(
            pa, pb, assertions, domain="grading",
            artifacts_dir=pa.parent / "artifacts", step=step_id)
        assert res.task_passed, (
            f"{step_id} failed={res.failed} rate={res.criterion_pass_rate}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
