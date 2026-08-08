-- Bundled seed A: inbox for GR-SEED-001

CREATE TABLE emails (
  email_id            TEXT PRIMARY KEY,
  sender              TEXT NOT NULL,
  subject             TEXT NOT NULL,
  body                TEXT NOT NULL,
  sent_at             TEXT NOT NULL,
  stated_total_points INTEGER,
  assignment_code     TEXT NOT NULL,
  is_messy            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE rubric_drafts (
  draft_id        TEXT PRIMARY KEY,
  email_id        TEXT NOT NULL,
  item_key        TEXT NOT NULL,
  description     TEXT NOT NULL,
  max_points      INTEGER NOT NULL,
  expected_key    TEXT NOT NULL,
  item_ord        INTEGER NOT NULL
);

CREATE TABLE audit_notes (
  note_id         TEXT PRIMARY KEY,
  note            TEXT,
  created_at      TEXT
);

-- Earlier messy email with wrong total and HTML noise
INSERT INTO emails VALUES
 ('EM-01', 'prof@university.edu', 'HW1 rubric (draft)',
  '<html>Ignore attachment rubric_v0.pdf — total is 8 somehow??</html>',
  '2026-02-01T09:00:00Z', 8, 'HW1', 1),
 ('EM-02', 'prof@university.edu', 'HW1 rubric FINAL',
  'Final rubric: Q1 correctness 5pts, Q2 explanation 5pts. Total 10.',
  '2026-02-02T14:00:00Z', 10, 'HW1', 0);

INSERT INTO rubric_drafts VALUES
 ('RD-01a', 'EM-01', 'Q1', 'Correctness (old)', 4, 'derivative', 1),
 ('RD-01b', 'EM-01', 'Q2', 'Explanation (old)', 4, 'chain rule', 2),
 ('RD-02a', 'EM-02', 'Q1', 'Correctness', 5, 'derivative', 1),
 ('RD-02b', 'EM-02', 'Q2', 'Explanation', 5, 'chain rule', 2);
