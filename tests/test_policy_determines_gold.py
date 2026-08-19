"""P5 acceptance test: POLICY_TEXT fully determines the grading score.

`_reference_score` below is transcribed independently from
envs/grading/policy.py's POLICY_TEXT (not imported from oracle.py) — the
point is to catch policy text drifting looser than what the oracle/rubric
actually implements, the exact failure the plan measured: a fully
policy-compliant Q1=2, Q2=2 grade used to score 24/26 and fail the task
because the old wording ("at most half") did not pin an exact value.
"""
from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from envs.grading.oracle import score_submission  # noqa: E402
from envs.grading.policy import POLICY_TEXT  # noqa: E402

MAX_POINTS = 5


def _reference_score(*, clarity: str, handwriting_noise: int, matches: bool) -> int:
    """Transcribed from POLICY_TEXT's 'Grading submissions' rule, independently
    of envs/grading/oracle.py's implementation."""
    if not matches:
        return 0
    if clarity == "low" or handwriting_noise == 1:
        return MAX_POINTS // 2
    return MAX_POINTS


CASES = list(product(("high", "low"), (0, 1), (True, False)))


@pytest.mark.parametrize("clarity,handwriting_noise,matches", CASES)
def test_policy_determines_gold(clarity, handwriting_noise, matches):
    sub = {
        "visible_answer": "derivative via chain rule" if matches else "unrelated text",
        "clarity": clarity,
        "handwriting_noise": handwriting_noise,
    }
    items = [{"item_key": "Q1", "expected_key": "derivative",
              "max_points": MAX_POINTS}]
    oracle_scores = score_submission(sub, items)
    expected = _reference_score(
        clarity=clarity, handwriting_noise=handwriting_noise, matches=matches)
    assert oracle_scores["Q1"] == expected, (
        f"clarity={clarity} noise={handwriting_noise} matches={matches}: "
        f"oracle gave {oracle_scores['Q1']}, policy-reference gives {expected}")


def test_policy_text_states_the_exact_rule():
    """Guard against the scoring rule regressing to the vague 'at most half'
    wording that leaves the score under-determined (P5's original bug). The
    regrade section's 'at most floor(...)' is a separate validity check on
    an already-graded state, not the scoring rule, so it's excluded here."""
    assert "at most half" not in POLICY_TEXT.lower()
    assert "halved and floored" in POLICY_TEXT
