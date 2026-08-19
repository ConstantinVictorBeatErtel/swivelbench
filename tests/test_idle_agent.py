"""P6 acceptance test: an agent that calls no tools must score 0.0.

This is a structural gate, not a one-off check on the seed task: it runs over
every grading task (E2E and @step) so it keeps catching vacuous
NOT EXISTS-over-empty-tables criteria as envs/grading/criteria.py's
CRITERION_TEMPLATES (and the WORLD_AXES scenario engine in
envs/grading/scenario.py) grow new negative/propagation criteria.
Before the fix, N1/N2/N3/N4 and X2/X5 passed for free on an untouched DB
because "nothing happened" trivially satisfies "nothing bad happened".
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import verifier  # noqa: E402
from envs.grading.task import all_tasks  # noqa: E402
from envs.registry import build_episode  # noqa: E402

GR_TASK_IDS = sorted(all_tasks().keys())


@pytest.mark.parametrize("task_id", GR_TASK_IDS)
def test_idle_agent_scores_zero(task_id):
    work = Path(tempfile.mkdtemp(prefix="sb_idle_gr_"))
    try:
        episode = build_episode(task_id, work, artifacts_dir=work / "artifacts")
        try:
            res = verifier.verify(
                episode.pa, episode.pb, episode.assertions,
                domain="grading", artifacts_dir=work / "artifacts",
                step=episode.step_id)
        finally:
            episode.api.close()
        assert res.criteria_total > 0, f"{task_id} scored zero active criteria"
        assert res.criterion_pass_rate == 0.0, (
            f"{task_id} idle agent scored {res.criterion_pass_rate} "
            f"(passed={res.passed})")
    finally:
        shutil.rmtree(work, ignore_errors=True)
