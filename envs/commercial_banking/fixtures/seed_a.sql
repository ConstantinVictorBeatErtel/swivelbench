-- Bundled seed A: credit_workbench for CB-SEED-001 / CB-L0-001

CREATE TABLE credit_requests (
  request_id      TEXT PRIMARY KEY,
  customer_name   TEXT NOT NULL,
  customer_email  TEXT,
  request_type    TEXT NOT NULL,
  limit_amount    REAL NOT NULL,
  status          TEXT NOT NULL,
  notes           TEXT
);

CREATE TABLE report_templates (
  template_id         TEXT PRIMARY KEY,
  request_type        TEXT NOT NULL,
  name                TEXT NOT NULL,
  required_sections   TEXT NOT NULL,
  corrupt             INTEGER NOT NULL DEFAULT 0,
  corrupt_kind        TEXT
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
  source          TEXT NOT NULL,
  digest_status   TEXT NOT NULL,
  as_of           TEXT NOT NULL,
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
  cell_key        TEXT NOT NULL,
  cell_value      REAL,
  PRIMARY KEY (model_id, cell_key)
);

CREATE TABLE spread_jobs (
  job_id          TEXT PRIMARY KEY,
  request_id      TEXT NOT NULL,
  model_id        TEXT NOT NULL,
  status          TEXT NOT NULL,
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

INSERT INTO credit_requests VALUES
 ('CRQ-1001', 'Northgate Logistics LLC', 'cfo@northgate.example',
  'revolving_credit', 2500000.0, 'open',
  'Annual revolver renewal; need credit memo.');

INSERT INTO report_templates VALUES
 ('TPL-REV-OK', 'revolving_credit', 'Revolver Credit Memo v3',
  'Executive Summary,Financial Analysis,Covenant Review,Recommendation',
  0, NULL),
 ('TPL-REV-BAD', 'revolving_credit', 'Revolver Credit Memo v2 (corrupt)',
  'Executive Summary,Recommendation',
  1, 'missing_sections'),
 ('TPL-TL-OK', 'term_loan', 'Term Loan Memo v1',
  'Executive Summary,Collateral,Financial Analysis,Recommendation',
  0, NULL);

INSERT INTO deals_archive VALUES
 ('ARC-01', 'Northgate Logistics LLC', 'REV-STD',
  'LEVERAGE <= 4.0 historically tight', 'SOFR+275 historically', 2024),
 ('ARC-02', 'Cascade Precision Inc', 'TL-STD',
  'DSCR >= 1.25', 'SOFR+300', 2023);

INSERT INTO web_digests VALUES
 ('DIG-CUR', 'Northgate Logistics LLC', 'web', 'current', '2026-01-15',
  42000000.0, 4150000.0, 15600000.0, 1180000.0),
 ('DIG-STALE', 'Northgate Logistics LLC', 'news', 'stale', '2024-12-01',
  38000000.0, 3900000.0, 14000000.0, 1100000.0),
 ('DIG-CONFLICT', 'Northgate Logistics LLC', 'news', 'current', '2026-01-10',
  42000000.0, 5000000.0, 15600000.0, 1180000.0);

INSERT INTO request_state VALUES
 ('CRQ-1001', NULL, NULL, NULL, NULL);
