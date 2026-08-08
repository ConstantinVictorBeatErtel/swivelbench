-- credit_workbench (system A)
CREATE TABLE credit_requests (
  request_id      TEXT PRIMARY KEY,
  customer_name   TEXT NOT NULL,
  customer_email  TEXT,
  request_type    TEXT NOT NULL,   -- e.g. revolving_credit
  limit_amount    REAL NOT NULL,
  status          TEXT NOT NULL,   -- open | in_progress | closed
  notes           TEXT
);

CREATE TABLE report_templates (
  template_id         TEXT PRIMARY KEY,
  request_type        TEXT NOT NULL,
  name                TEXT NOT NULL,
  required_sections   TEXT NOT NULL,  -- comma-separated section titles
  corrupt             INTEGER NOT NULL DEFAULT 0,
  corrupt_kind        TEXT            -- missing_sections | swapped_order | null
);

CREATE TABLE deals_archive (
  archive_id      TEXT PRIMARY KEY,
  customer_name   TEXT NOT NULL,
  product_code    TEXT,
  covenant_notes  TEXT,
  pricing_notes   TEXT,
  closed_fy       INTEGER
);

CREATE TABLE web_digests (
  digest_id       TEXT PRIMARY KEY,
  customer_name   TEXT NOT NULL,
  source          TEXT NOT NULL,   -- web | news
  digest_status   TEXT NOT NULL,   -- current | stale
  as_of           TEXT NOT NULL,   -- YYYY-MM-DD
  revenue         REAL,
  ebitda          REAL,
  total_debt      REAL,
  interest_expense REAL
);

CREATE TABLE excel_models (
  model_id        TEXT PRIMARY KEY,
  request_id      TEXT NOT NULL,
  digest_id       TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE model_cells (
  model_id        TEXT NOT NULL,
  cell_key        TEXT NOT NULL,   -- revenue|ebitda|total_debt|interest_expense|leverage
  cell_value      REAL,
  PRIMARY KEY (model_id, cell_key)
);

CREATE TABLE spread_jobs (
  job_id          TEXT PRIMARY KEY,
  request_id      TEXT NOT NULL,
  model_id        TEXT NOT NULL,
  status          TEXT NOT NULL,   -- submitted | returned | checked
  injected_error  INTEGER NOT NULL DEFAULT 0,
  submitted_at    TEXT,
  returned_at     TEXT,
  checked_at      TEXT
);

CREATE TABLE spread_lines (
  job_id          TEXT NOT NULL,
  line_key        TEXT NOT NULL,
  line_value      REAL,
  corrected       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (job_id, line_key)
);

CREATE TABLE report_sections (
  request_id      TEXT NOT NULL,
  template_id     TEXT NOT NULL,
  section_title   TEXT NOT NULL,
  section_body    TEXT NOT NULL,
  section_ord     INTEGER NOT NULL,
  PRIMARY KEY (request_id, section_title)
);

CREATE TABLE request_state (
  request_id      TEXT PRIMARY KEY,
  selected_template_id TEXT,
  selected_customer_id TEXT,
  model_id        TEXT,
  spread_job_id   TEXT
);

CREATE TABLE audit_notes (
  note_id         TEXT PRIMARY KEY,
  request_id      TEXT,
  note            TEXT,
  created_at      TEXT
);
