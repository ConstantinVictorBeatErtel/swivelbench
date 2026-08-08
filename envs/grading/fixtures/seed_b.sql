-- Bundled seed B: gradescope for GR-SEED-001

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
  clarity         TEXT NOT NULL,
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
  claim_type      TEXT NOT NULL,
  claim_text      TEXT,
  status          TEXT NOT NULL,
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

INSERT INTO courses VALUES ('CSE101', 'Intro Calculus');
INSERT INTO assignments VALUES ('ASN-HW1', 'CSE101', 'HW1', 'Homework 1');

INSERT INTO students VALUES
 ('U-100', 'Alex Kim', 'alex.kim@university.edu'),
 ('U-101', 'Alex Kimm', 'alex.kimm@university.edu'),
 ('U-102', 'Jordan Lee', 'jordan.lee@university.edu'),
 ('U-103', 'Sam Patel', 'sam.patel@university.edu');

INSERT INTO submissions VALUES
 ('SUB-1', 'ASN-HW1', 'U-100',
  'Used the derivative and chain rule correctly.', 'high', 0),
 ('SUB-2', 'ASN-HW1', 'U-102',
  'smudged ink ... derivative maybe?', 'low', 1),
 ('SUB-3', 'ASN-HW1', 'U-103',
  'I discussed photosynthesis instead.', 'high', 0);

INSERT INTO regrade_requests VALUES
 ('RG-1', 'SUB-3', 'out_of_rubric',
  'Please give me points for creativity', 'open', NULL, NULL),
 ('RG-2', 'SUB-1', 'arithmetic',
  'My item scores do not add up', 'open', NULL, NULL);
