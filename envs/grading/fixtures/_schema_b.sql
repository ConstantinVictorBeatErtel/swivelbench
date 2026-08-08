-- gradescope (system B)
CREATE TABLE courses (
  course_id       TEXT PRIMARY KEY,
  name            TEXT NOT NULL
);

CREATE TABLE assignments (
  assignment_id   TEXT PRIMARY KEY,
  course_id       TEXT NOT NULL,
  code            TEXT NOT NULL,
  title           TEXT NOT NULL
);

CREATE TABLE students (
  user_id         TEXT PRIMARY KEY,
  display_name    TEXT NOT NULL,
  email           TEXT NOT NULL
);

CREATE TABLE submissions (
  submission_id   TEXT PRIMARY KEY,
  assignment_id   TEXT NOT NULL,
  user_id         TEXT NOT NULL,
  visible_answer  TEXT,
  clarity         TEXT NOT NULL,   -- high | low
  handwriting_noise INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE rubrics (
  rubric_id       TEXT PRIMARY KEY,
  assignment_id   TEXT NOT NULL,
  total_points    INTEGER NOT NULL,
  published_at    TEXT NOT NULL,
  source_email_id TEXT
);

CREATE TABLE rubric_items (
  rubric_id       TEXT NOT NULL,
  item_key        TEXT NOT NULL,
  description     TEXT NOT NULL,
  max_points      INTEGER NOT NULL,
  expected_key    TEXT NOT NULL,
  item_ord        INTEGER NOT NULL,
  PRIMARY KEY (rubric_id, item_key)
);

CREATE TABLE grades (
  grade_id        TEXT PRIMARY KEY,
  submission_id   TEXT NOT NULL,
  user_id         TEXT NOT NULL,
  grade_total     INTEGER NOT NULL,
  comment         TEXT,
  graded_at       TEXT NOT NULL
);

CREATE TABLE grade_items (
  grade_id        TEXT NOT NULL,
  item_key        TEXT NOT NULL,
  points          INTEGER NOT NULL,
  PRIMARY KEY (grade_id, item_key)
);

CREATE TABLE regrade_requests (
  regrade_id      TEXT PRIMARY KEY,
  submission_id   TEXT NOT NULL,
  claim_type      TEXT NOT NULL,  -- out_of_rubric | arithmetic | clarity_partial
  claim_text      TEXT,
  status          TEXT NOT NULL,  -- open | upheld | adjusted
  resolution_note TEXT,
  resolved_at     TEXT
);

CREATE TABLE audit_log (
  entry_id        TEXT PRIMARY KEY,
  actor           TEXT NOT NULL,
  action          TEXT NOT NULL,
  target_system   TEXT NOT NULL,
  target_key      TEXT NOT NULL,
  note            TEXT,
  created_at      TEXT NOT NULL
);
