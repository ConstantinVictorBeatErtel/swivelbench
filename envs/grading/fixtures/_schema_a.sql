-- inbox (system A)
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
