"""Adversarial LLM-verifier calibration loop for non-SQL rubric criteria.

Flow (ComplexConstraints §3.3):
  1. Author drafts criterion + reference artifact
  2. Author hand-grades the reference (expected: pass|fail)
  3. LLM verifier grades; on disagreement, tighten criterion wording
  4. Adversarially flip the artifact so the correct verdict flips; confirm
     the verifier flips with it
  5. Mark calibrated=true only when both directions agree

Deterministic SQL/OOXML criteria do not use this loop.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


JudgeFn = Callable[[str, str], bool]  # (criterion_text, artifact_text) -> passed


@dataclass
class CalibrationCase:
    criterion_id: str
    criterion_text: str
    reference_artifact: str
    hand_label_pass: bool
    adversarial_artifact: str
    adversarial_label_pass: bool
    calibrated: bool = False
    notes: list[str] = field(default_factory=list)
    judge_reference: bool | None = None
    judge_adversarial: bool | None = None


def calibrate(
    case: CalibrationCase,
    judge: JudgeFn,
) -> CalibrationCase:
    """Run the draft → hand-grade → judge → flip-test loop once."""
    case.notes = list(case.notes)
    case.judge_reference = bool(judge(case.criterion_text, case.reference_artifact))
    if case.judge_reference != case.hand_label_pass:
        case.calibrated = False
        case.notes.append(
            "Judge disagreed with hand label on reference; tighten criterion "
            f"(hand={case.hand_label_pass}, judge={case.judge_reference})."
        )
        return case

    case.judge_adversarial = bool(
        judge(case.criterion_text, case.adversarial_artifact))
    if case.judge_adversarial != case.adversarial_label_pass:
        case.calibrated = False
        case.notes.append(
            "Judge failed adversarial flip-test "
            f"(expected={case.adversarial_label_pass}, "
            f"judge={case.judge_adversarial})."
        )
        return case

    case.calibrated = True
    case.notes.append("Calibrated: reference and adversarial both agree.")
    return case


def heuristic_structure_judge(criterion_text: str, artifact_text: str) -> bool:
    """Offline stand-in judge for smoke tests (not for scored criteria).

    Passes when every quoted or ALLCAPS token from the criterion that looks
    like a required heading appears in the artifact. Real deployments should
    pass an LLM judge instead.
    """
    import re
    needles = re.findall(r'"([^"]+)"', criterion_text)
    if not needles:
        needles = re.findall(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)\b",
                             criterion_text)
    if not needles:
        return bool(artifact_text.strip())
    art = artifact_text.lower()
    return all(n.lower() in art for n in needles)


def _demo() -> int:
    case = CalibrationCase(
        criterion_id="LLM-F2-demo",
        criterion_text=(
            'Credit memo must include headings "Executive Summary" and '
            '"Recommendation" with non-empty bodies.'
        ),
        reference_artifact=(
            "Executive Summary\nSolid revolving request.\n"
            "Recommendation\nApprove with covenants.\n"
        ),
        hand_label_pass=True,
        adversarial_artifact="Executive Summary\n\n",  # missing Recommendation
        adversarial_label_pass=False,
    )
    out = calibrate(case, heuristic_structure_judge)
    print(json.dumps(asdict(out), indent=2))
    return 0 if out.calibrated else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true",
                    help="Run offline heuristic calibration smoke demo")
    ap.add_argument("--case", type=Path,
                    help="JSON CalibrationCase to evaluate with --judge=heuristic")
    ap.add_argument("--judge", choices=("heuristic",), default="heuristic")
    args = ap.parse_args(argv)
    if args.demo:
        return _demo()
    if args.case:
        data = json.loads(args.case.read_text())
        case = CalibrationCase(**data)
        judge = heuristic_structure_judge
        out = calibrate(case, judge)
        print(json.dumps(asdict(out), indent=2))
        return 0 if out.calibrated else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
