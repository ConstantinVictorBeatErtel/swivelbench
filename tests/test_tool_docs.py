"""P2 acceptance test: tool descriptions must not overclaim audit behaviour.

Only log_action writes envs/grading's audit_log; list_submissions and
resolve_regrade previously claimed their calls were "recorded" /
"automatically" logged, which let an agent skip the graded log_action calls
entirely for S2_queue/S4_regrades and still believe it was compliant.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from envs.grading.tools import make_tools  # noqa: E402

AUDIT_WRITING_TOOLS = {"log_action"}
OVERCLAIM_RE = re.compile(r"\brecorded\b|\bautomatically\b", re.IGNORECASE)


def test_tool_descriptions_do_not_promise_audit():
    offenders = []
    for t in make_tools():
        name = t["function"]["name"]
        desc = t["function"]["description"]
        if name in AUDIT_WRITING_TOOLS:
            continue
        if OVERCLAIM_RE.search(desc):
            offenders.append((name, desc))
    assert not offenders, offenders
