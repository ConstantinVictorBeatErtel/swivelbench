-- Assertions for GR-SEED-001
-- Winning email EM-02, total 10, items Q1=5 Q2=5
-- SUB-1 full 10; SUB-2 unclear => at most 5 total (2+2 or 2+3 half of 5 floor=2 each = 4);
--   policy: at most half max_points floor to int => 2 per item if match, else 0.
--   SUB-2 visible has "deriv" matching derivative => Q1=2; "chain rule" not present => Q2=0; total=2
-- SUB-3 no match => 0
-- Regrade RG-1 upheld; RG-2 arithmetic — after correct grading sums match so uphold or adjust to sum
--
-- Facet taxonomy adapted from BankerToolBench multi-part / structural completeness
-- patterns → dual-DB SQL only. File-format check F1 lives in core/format_check.py
-- (docs/format_judgement.md). No LLM judge in the default scorer.

-- ===== Step: read prof emails / publish rubric =====
-- @assert id=P1 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.rubrics
  WHERE assignment_id = 'ASN-HW1' AND total_points = 10
    AND source_email_id = 'EM-02'
);

-- @assert id=P2 kind=positive weight=1.0
SELECT (
  SELECT COUNT(*) FROM b.rubric_items ri
  JOIN b.rubrics r ON r.rubric_id = ri.rubric_id
  WHERE r.assignment_id = 'ASN-HW1'
) = 2;

-- @assert id=X1 kind=propagation weight=1.0
SELECT EXISTS (
  SELECT 1 FROM a.emails e
  JOIN b.rubrics r ON r.source_email_id = e.email_id
  WHERE e.email_id = 'EM-02' AND r.total_points = e.stated_total_points
);

-- @assert id=X3 kind=propagation weight=1.0
SELECT (
  SELECT SUM(ri.max_points) FROM b.rubric_items ri
  JOIN b.rubrics r ON r.rubric_id = ri.rubric_id
  WHERE r.assignment_id = 'ASN-HW1'
) = (
  SELECT total_points FROM b.rubrics WHERE assignment_id = 'ASN-HW1'
);

-- @assert id=X4 kind=propagation weight=1.0
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

-- @assert id=N1 kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.rubrics WHERE source_email_id = 'EM-01'
);

-- @assert id=T1 kind=trail weight=1.0 critical=true
SELECT EXISTS (
  SELECT 1 FROM b.audit_log WHERE action = 'publish_rubric'
);

-- ===== Step: open Gradescope submissions =====
-- @assert id=P9 kind=positive weight=1.0
SELECT (
  SELECT COUNT(*) FROM b.grades g
  JOIN b.submissions s ON s.submission_id = g.submission_id
  WHERE s.assignment_id = 'ASN-HW1'
) = 3;

-- @assert id=N2 kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-1' AND user_id = 'U-101'
);

-- @assert id=T5 kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'open_submissions' AND target_key = 'ASN-HW1'
);

-- ===== Step: grade each submission (totals + item facets + clarity cap) =====
-- @assert id=P3 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-1' AND user_id = 'U-100' AND grade_total = 10
);

-- @assert id=P4 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-2' AND user_id = 'U-102' AND grade_total = 2
);

-- @assert id=P5 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-3' AND user_id = 'U-103' AND grade_total = 0
);

-- @assert id=P7 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-1' AND gi.item_key = 'Q1' AND gi.points = 5
) AND EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-1' AND gi.item_key = 'Q2' AND gi.points = 5
);

-- @assert id=P8 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-2' AND gi.item_key = 'Q1' AND gi.points = 2
) AND EXISTS (
  SELECT 1 FROM b.grade_items gi
  JOIN b.grades g ON g.grade_id = gi.grade_id
  WHERE g.submission_id = 'SUB-2' AND gi.item_key = 'Q2' AND gi.points = 0
);

-- @assert id=X2 kind=propagation weight=1.0
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades g
  WHERE g.grade_total != (
    SELECT COALESCE(SUM(gi.points), 0) FROM b.grade_items gi
    WHERE gi.grade_id = g.grade_id
  )
);

-- @assert id=X5 kind=propagation weight=1.0
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades g
  WHERE (
    SELECT COUNT(*) FROM b.grade_items gi WHERE gi.grade_id = g.grade_id
  ) != 2
);

-- @assert id=N3 kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.grades
  WHERE submission_id = 'SUB-2' AND grade_total > 5
);

-- @assert id=T2 kind=trail weight=1.0 critical=true
SELECT EXISTS (
  SELECT 1 FROM b.audit_log WHERE action = 'grade_item'
);

-- ===== Step: deal with regrade requests =====
-- @assert id=P6 kind=positive weight=1.0
SELECT (
  SELECT COUNT(*) FROM b.regrade_requests WHERE status != 'open'
) = 2;

-- @assert id=P10 kind=positive weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.regrade_requests
  WHERE regrade_id = 'RG-1' AND status = 'upheld'
) AND EXISTS (
  SELECT 1 FROM b.regrade_requests
  WHERE regrade_id = 'RG-2' AND status = 'upheld'
);

-- @assert id=N4 kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.regrade_requests
  WHERE regrade_id = 'RG-1' AND status = 'adjusted'
);

-- @assert id=N5 kind=negative weight=1.0 critical=true
SELECT NOT EXISTS (
  SELECT 1 FROM b.regrade_requests WHERE status = 'open'
);

-- @assert id=T3 kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'resolve_regrade' AND target_key = 'RG-1'
);

-- @assert id=T4 kind=trail weight=1.0
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'resolve_regrade' AND target_key = 'RG-2'
);
