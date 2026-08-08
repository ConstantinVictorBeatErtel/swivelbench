"""Adversarial gate for commercial banking and grading.

Wrong states are built by perturbing a correct oracle rollout through the real
action API. No wrong state may achieve task_passed.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.commercial_banking import oracle as cb_oracle  # noqa: E402
from envs.commercial_banking.runtime import make_api as cb_make_api  # noqa: E402
from envs.commercial_banking.runtime import prepare as cb_prepare  # noqa: E402
from envs.commercial_banking.task import SEED_TASK as CB_SEED  # noqa: E402
from envs.grading import oracle as gr_oracle  # noqa: E402
from envs.grading.runtime import make_api as gr_make_api  # noqa: E402
from envs.grading.runtime import prepare as gr_prepare  # noqa: E402
from envs.grading.task import SEED_TASK as GR_SEED  # noqa: E402


class Drop:
    def __init__(self, api, *drop: str) -> None:
        self._api, self._drop = api, set(drop)

    def __getattr__(self, name: str):
        if name in self._drop:
            return lambda *a, **k: {"ok": True, "suppressed": True}
        return getattr(self._api, name)


def _score_cb(build, flags=None):
    work = Path(tempfile.mkdtemp(prefix="sb_adv_cb_"))
    try:
        pa, pb, assertions = cb_prepare(CB_SEED, work)
        api = cb_make_api(pa, pb, CB_SEED)
        cb_oracle.FLAGS.clear()
        cb_oracle.FLAGS.update(flags or {})
        try:
            build(api)
        finally:
            cb_oracle.FLAGS.clear()
        api.close()
        return verifier.verify(pa, pb, assertions,
                               domain="commercial_banking",
                               artifacts_dir=pa.parent / "artifacts")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _score_gr(build, flags=None):
    work = Path(tempfile.mkdtemp(prefix="sb_adv_gr_"))
    try:
        pa, pb, assertions = gr_prepare(GR_SEED, work)
        api = gr_make_api(pa, pb, GR_SEED)
        gr_oracle.FLAGS.clear()
        gr_oracle.FLAGS.update(flags or {})
        try:
            build(api)
        finally:
            gr_oracle.FLAGS.clear()
        api.close()
        return verifier.verify(pa, pb, assertions,
                               domain="grading",
                               artifacts_dir=pa.parent / "artifacts")
    finally:
        shutil.rmtree(work, ignore_errors=True)


CB_WRONG = [
    ("cb_no_trail", lambda api: cb_oracle.run(Drop(api, "log_action")), None),
    ("cb_corrupt_template", cb_oracle.run, {"use_corrupt_template": True}),
    ("cb_skip_spread", cb_oracle.run, {"skip_spread_check": True}),
    ("cb_write_archived", cb_oracle.run, {"write_archived": True}),
    ("cb_use_stale", cb_oracle.run, {"use_stale": True}),
    ("cb_matured_product", cb_oracle.run, {"use_matured_product": True}),
]

GR_WRONG = [
    ("gr_no_trail", lambda api: gr_oracle.run(Drop(api, "log_action")), None),
    ("gr_messy_email", gr_oracle.run, {"use_messy_email": True}),
    ("gr_wrong_student", gr_oracle.run, {"wrong_student": True}),
    ("gr_skip_regrades", gr_oracle.run, {"skip_regrades": True}),
    ("gr_grant_bait", gr_oracle.run, {"grant_bait": True}),
    ("gr_full_unclear", gr_oracle.run, {"full_credit_unclear": True}),
]


def test_cb_oracle_perfect():
    res = _score_cb(cb_oracle.run)
    assert res.task_passed, res.failed
    assert res.criterion_pass_rate == 1.0


def test_gr_oracle_perfect():
    res = _score_gr(gr_oracle.run)
    assert res.task_passed, res.failed
    assert res.criterion_pass_rate == 1.0


@pytest.mark.parametrize("name,build,flags", CB_WRONG, ids=[w[0] for w in CB_WRONG])
def test_cb_wrong_states_not_passed(name, build, flags):
    res = _score_cb(build, flags)
    assert not res.task_passed, (
        f"{name} achieved task_passed; reward is blind. failed={res.failed}")
    assert res.criterion_pass_rate < 1.0


@pytest.mark.parametrize("name,build,flags", GR_WRONG, ids=[w[0] for w in GR_WRONG])
def test_gr_wrong_states_not_passed(name, build, flags):
    res = _score_gr(build, flags)
    assert not res.task_passed, (
        f"{name} achieved task_passed; reward is blind. failed={res.failed}")
    assert res.criterion_pass_rate < 1.0
