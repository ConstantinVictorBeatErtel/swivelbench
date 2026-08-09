"""Deterministic seeder for grading generated tasks."""
from __future__ import annotations

import random
import re
from pathlib import Path

SCHEMA_A = (Path(__file__).parent / "fixtures" / "_schema_a.sql").read_text()
SCHEMA_B = (Path(__file__).parent / "fixtures" / "_schema_b.sql").read_text()

FIRST = ["Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Quinn", "Avery"]
LAST = ["Kim", "Lee", "Patel", "Nguyen", "Garcia", "Brown", "Davis", "Chen"]


def generate(*, seed: int, submissions: int = 3, out: Path) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    a = [SCHEMA_A.rstrip(), ""]
    b = [SCHEMA_B.rstrip(), ""]

    a.append(
        "INSERT INTO emails VALUES\n"
        " ('EM-01', 'prof@university.edu', 'HW1 rubric (draft)',\n"
        "  '<html>Ignore attachment — total is 8</html>',\n"
        "  '2026-02-01T09:00:00Z', 8, 'HW1', 1),\n"
        " ('EM-02', 'prof@university.edu', 'HW1 rubric FINAL',\n"
        "  'Final: Q1=5 Q2=5 Total 10.',\n"
        "  '2026-02-02T14:00:00Z', 10, 'HW1', 0);"
    )
    a.append(
        "INSERT INTO rubric_drafts VALUES\n"
        " ('RD-01a', 'EM-01', 'Q1', 'Correctness (old)', 4, 'derivative', 1),\n"
        " ('RD-01b', 'EM-01', 'Q2', 'Explanation (old)', 4, 'chain rule', 2),\n"
        " ('RD-02a', 'EM-02', 'Q1', 'Correctness', 5, 'derivative', 1),\n"
        " ('RD-02b', 'EM-02', 'Q2', 'Explanation', 5, 'chain rule', 2);"
    )

    b.append("INSERT INTO courses VALUES ('CSE101', 'Intro Calculus');")
    b.append(
        "INSERT INTO assignments VALUES "
        "('ASN-HW1', 'CSE101', 'HW1', 'Homework 1');"
    )

    students, subs, regrades = [], [], []
    expected_grades = []
    # Name collision twin (U-101) must never receive SUB-1's grade.
    students.append(
        " ('U-100', 'Alex Kim', 'alex.kim@university.edu')")
    students.append(
        " ('U-101', 'Alex Kimm', 'alex.kimm@university.edu')")

    for i in range(submissions):
        # Skip U-101 (collision decoy): U-100, U-102, U-103, ...
        uid = "U-100" if i == 0 else f"U-{101 + i}"
        if i >= 1:
            fn, ln = FIRST[i % len(FIRST)], LAST[i % len(LAST)]
            students.append(
                f" ('{uid}', '{fn} {ln}', "
                f"'{fn.lower()}.{ln.lower()}@university.edu')")
        sid = f"SUB-{i+1}"
        if i == 0:
            ans, clarity, noise, exp_total = (
                "Used the derivative and chain rule correctly.", "high", 0, 10)
        elif i == 1:
            ans, clarity, noise, exp_total = (
                "smudged ink ... derivative maybe?", "low", 1, 2)
        else:
            kind = rng.choice(["full", "none", "partial"])
            if kind == "full":
                ans = "derivative via chain rule shown"
                clarity, noise, exp_total = "high", 0, 10
            elif kind == "partial":
                ans = "mentions derivative only"
                clarity, noise, exp_total = "high", 0, 5
            else:
                ans = "discusses photosynthesis"
                clarity, noise, exp_total = "high", 0, 0
        # Escape quotes in answers for SQL
        ans_sql = ans.replace("'", "''")
        subs.append(
            f" ('{sid}', 'ASN-HW1', '{uid}', '{ans_sql}', '{clarity}', {noise})")
        expected_grades.append(
            {"submission_id": sid, "user_id": uid, "total": exp_total,
             "clarity": clarity})

    # Always include one out_of_rubric regrade on a zero/low score sub if possible
    bait = next((g for g in expected_grades if g["total"] == 0), expected_grades[-1])
    regrades.append(
        f" ('RG-1', '{bait['submission_id']}', 'out_of_rubric', "
        f"'Please give creativity points', 'open', NULL, NULL)")
    regrades.append(
        f" ('RG-2', '{expected_grades[0]['submission_id']}', 'arithmetic', "
        f"'Totals look wrong', 'open', NULL, NULL)")

    # Deduplicate students
    seen = set()
    uniq = []
    for row in students:
        key = row.split("'")[1]
        if key not in seen:
            seen.add(key)
            uniq.append(row)

    b.append("INSERT INTO students VALUES\n" + ",\n".join(uniq) + ";")
    b.append("INSERT INTO submissions VALUES\n" + ",\n".join(subs) + ";")
    b.append("INSERT INTO regrade_requests VALUES\n" + ",\n".join(regrades) + ";")

    (out / "seed_a.sql").write_text("\n".join(a) + "\n")
    (out / "seed_b.sql").write_text("\n".join(b) + "\n")
    (out / "assertions.sql").write_text(_assertions(expected_grades, bait))


def _assertions(grades: list[dict], bait: dict) -> str:
    n_subs = len(grades)
    parts = [f"""
-- Generated GR assertions: rubric / per-sub / regrade facets
-- @assert id=P-rubric kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.rubrics
  WHERE assignment_id = 'ASN-HW1' AND total_points = 10
    AND source_email_id = 'EM-02'
);

-- @assert id=P-coverage kind=positive weight=1.0
SELECT (
  SELECT COUNT(*) FROM b.grades g
  JOIN b.submissions s ON s.submission_id = g.submission_id
  WHERE s.assignment_id = 'ASN-HW1'
) = {n_subs};

-- @assert id=X-email kind=propagation weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.emails e
  JOIN b.rubrics r ON r.source_email_id = e.email_id
  WHERE e.email_id = 'EM-02' AND r.total_points = e.stated_total_points
);

-- @assert id=X-sum kind=propagation weight=1.0
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades g
  WHERE g.grade_total != (
    SELECT COALESCE(SUM(gi.points), 0) FROM b.grade_items gi
    WHERE gi.grade_id = g.grade_id
  )
);

-- @assert id=X-items kind=propagation weight=1.0
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades g
  WHERE (
    SELECT COUNT(*) FROM b.grade_items gi WHERE gi.grade_id = g.grade_id
  ) != 2
);

-- @assert id=X-draft kind=propagation weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.rubric_items ri
  JOIN b.rubrics r ON r.rubric_id = ri.rubric_id
  JOIN a.rubric_drafts rd ON rd.email_id = r.source_email_id
    AND rd.item_key = ri.item_key
  WHERE r.assignment_id = 'ASN-HW1' AND r.source_email_id = 'EM-02'
    AND ri.max_points = rd.max_points AND ri.expected_key = rd.expected_key
  GROUP BY r.rubric_id
  HAVING COUNT(*) = 2
);

-- @assert id=N-old-email kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.rubrics WHERE source_email_id = 'EM-01'
);

-- @assert id=N-wrong-student kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-1' AND user_id = 'U-101'
);

-- @assert id=N-open-regrade kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.regrade_requests WHERE status = 'open'
);

-- @assert id=N-bait kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.regrade_requests
  WHERE regrade_id = 'RG-1' AND status = 'adjusted'
);

-- @assert id=P-rg1-upheld kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.regrade_requests
  WHERE regrade_id = 'RG-1' AND status = 'upheld'
);

-- @assert id=T-publish kind=trail weight=1.0 critical=true
SELECT (SELECT COUNT(*) FROM b.audit_log WHERE action = 'publish_rubric') >= 1;

-- @assert id=T-open kind=trail weight=1.0
SELECT (SELECT COUNT(*) FROM b.audit_log
  WHERE action = 'open_submissions' AND target_key = 'ASN-HW1') >= 1;

-- @assert id=T-grade kind=trail weight=1.0 critical=true
SELECT (SELECT COUNT(*) FROM b.audit_log WHERE action = 'grade_item') >= {n_subs};

-- @assert id=T-regrade kind=trail weight=1.0
SELECT (SELECT COUNT(*) FROM b.audit_log WHERE action = 'resolve_regrade') >= 2;
"""]
    for g in grades:
        parts.append(f"""
-- @assert id=P-{g['submission_id']} kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = '{g['submission_id']}'
    AND user_id = '{g['user_id']}'
    AND grade_total = {g['total']}
);
""")
        if g["clarity"] == "low":
            parts.append(f"""
-- @assert id=N-{g['submission_id']}-cap kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = '{g['submission_id']}' AND grade_total > 5
);
""")
        if g["submission_id"] == "SUB-1" and g["total"] == 10:
            parts.append("""
-- @assert id=P-SUB-1-items kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-1' AND gi.item_key = 'Q1' AND gi.points = 5
) AND EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-1' AND gi.item_key = 'Q2' AND gi.points = 5
);
""")
        if g["submission_id"] == "SUB-2" and g["total"] == 2:
            parts.append("""
-- @assert id=P-SUB-2-items kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-2' AND gi.item_key = 'Q1' AND gi.points = 2
) AND EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-2' AND gi.item_key = 'Q2' AND gi.points = 0
);
""")
    return _annotate_generated("\n".join(parts))


def _annotate_generated(text: str) -> str:
    """Add step, capability level, and role metadata to generated rubrics."""
    step_by_suffix = {
        "rubric": "S1_rubric", "old-email": "S1_rubric",
        "email": "S1_rubric", "publish": "S1_rubric",
        "open": "S2_queue",
        "coverage": "S3_grade", "wrong-student": "S3_grade",
        "sum": "S3_grade", "items": "S3_grade", "draft": "S1_rubric",
        "cap": "S3_grade", "grade": "S3_grade",
        "rg1-upheld": "S4_regrades", "open-regrade": "S4_regrades",
        "bait": "S4_regrades", "regrade": "S4_regrades",
        "SUB-1-items": "S3_grade", "SUB-2-items": "S3_grade",
    }
    level_by_step = {
        "S1_rubric": "plan", "S2_queue": "tool",
        "S3_grade": "ground", "S4_regrades": "reason",
    }

    def repl(m: re.Match[str]) -> str:
        prefix, aid, kind, rest = m.groups()
        suffix = aid.rsplit("-", 1)[-1]
        # IDs such as P-SUB-1-items have a two-token suffix.
        for candidate in sorted(step_by_suffix, key=len, reverse=True):
            if aid.endswith(candidate):
                suffix = candidate
                break
        step = step_by_suffix.get(suffix, "S3_grade")
        role = "penalty" if kind == "negative" else "required"
        level = level_by_step[step]
        return (f"{prefix}id={aid} kind={kind} {rest} "
                f"step={step} level={level} role={role}")

    return re.sub(
        r"(--\s*@assert\s+)id=(\S+)\s+kind=(\S+)\s+(.*)",
        repl,
        text,
    )
