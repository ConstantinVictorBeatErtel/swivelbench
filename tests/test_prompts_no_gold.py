"""P4 acceptance test: step and E2E prompts must not leak the answer key.

Before the fix, envs/grading/steps.py's step prompts stated literal gold
values ("rubric from EM-02, total 10", "SUB-2 total not > 5") in a "Graded
checklist" section — an agent could pass by pattern-matching the prompt
without reconciling anything. Prompts must describe *capabilities* being
graded, not values.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from envs.grading.scenario import make_scenario  # noqa: E402
from envs.grading.steps import STEP_SPECS  # noqa: E402
from envs.grading.task import E2E_TASKS  # noqa: E402

# GR-SEED-001's bundled-fixture gold literals (envs/grading/fixtures/*.sql) —
# hand-enumerated since the bundled task doesn't go through the scenario
# engine and so has no sc.gold manifest to check against.
SEED_TASK_GOLD_LITERALS = [
    "EM-01", "EM-02", "SUB-1", "SUB-2", "SUB-3", "U-100", "U-101",
    "RG-1", "RG-2", "RUB-", "GRD-",
]
# Numbers only leak meaning in context ("total 10", "not > 5") — bare digits
# are too common in prose to ban outright, so check specific known-answer
# phrasings instead.
SEED_TASK_GOLD_PHRASES = [
    "total 10", "total is 10", "total=10",
    "SUB-2 total", "not > 5", "two items matching",
]


def test_step_prompts_contain_no_seed_task_gold():
    for step_id, spec in STEP_SPECS.items():
        text = spec.prompt
        for lit in SEED_TASK_GOLD_LITERALS:
            assert lit not in text, f"{step_id} prompt leaks {lit!r}"
        for phrase in SEED_TASK_GOLD_PHRASES:
            assert phrase.lower() not in text.lower(), (
                f"{step_id} prompt leaks phrase {phrase!r}")


def test_step_prompts_contain_no_generated_scenario_gold():
    """Cross-check against several sampled scenarios' actual gold manifests
    too, since step prompts are shared across every step-episode regardless
    of which scenario ultimately backs it."""
    offenders = []
    for seed in range(80001, 80011):
        sc = make_scenario(seed=seed, split="train", difficulty=3)
        gold_ids = [sc.gold["winning_email_id"]]
        gold_ids += list(sc.gold["graded_submissions"])
        gold_ids += [sg["user_id"] for sg in sc.gold["graded_submissions"].values()]
        for step_id, spec in STEP_SPECS.items():
            for lit in gold_ids:
                if lit and lit in spec.prompt:
                    offenders.append((seed, step_id, lit))
    assert not offenders, offenders[:20]


def test_e2e_prompts_contain_no_gold():
    for task_id, task in E2E_TASKS.items():
        if task.use_bundled_fixtures:
            for lit in SEED_TASK_GOLD_LITERALS:
                assert lit not in task.prompt, f"{task_id} prompt leaks {lit!r}"
            continue
        sc = make_scenario(seed=task.seed, split="train", difficulty=task.difficulty)
        gold_ids = [sc.gold["winning_email_id"]] + list(sc.gold["graded_submissions"])
        for lit in gold_ids:
            assert lit not in task.prompt, f"{task_id} prompt leaks {lit!r}"


def test_step_prompts_state_policy_not_just_checklist():
    """De-leaking the checklist only helps if the policy that actually
    determines scores is still reachable from the prompt (Phase 1's P5 fix
    is a prerequisite here, per the plan's own sequencing note)."""
    for step_id, spec in STEP_SPECS.items():
        assert "POLICY" in spec.prompt, f"{step_id} prompt has no policy text"
        assert "Graded checklist" not in spec.prompt, (
            f"{step_id} prompt still has a literal-value checklist")
