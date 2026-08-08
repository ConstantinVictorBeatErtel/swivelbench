-- Bundled seed B: ncino_core for CB-SEED-001 / CB-L0-001

CREATE TABLE customers (
  customer_id     TEXT PRIMARY KEY,
  legal_name      TEXT NOT NULL,
  tin             TEXT,
  contact_email   TEXT,
  record_status   TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE credit_products (
  product_code    TEXT PRIMARY KEY,
  request_type    TEXT NOT NULL,
  name            TEXT NOT NULL,
  status          TEXT NOT NULL,
  rate_bps        INTEGER NOT NULL,
  fee_bps         INTEGER NOT NULL
);

CREATE TABLE covenants (
  covenant_id     TEXT PRIMARY KEY,
  product_code    TEXT NOT NULL,
  covenant_type   TEXT NOT NULL,
  operator        TEXT NOT NULL,
  threshold       REAL NOT NULL,
  status          TEXT NOT NULL
);

CREATE TABLE deals (
  deal_id         TEXT PRIMARY KEY,
  request_id      TEXT NOT NULL,
  customer_id     TEXT NOT NULL,
  product_code    TEXT NOT NULL,
  limit_amount    REAL NOT NULL,
  template_id     TEXT,
  status          TEXT NOT NULL,
  pushed_at       TEXT
);

CREATE TABLE system_covenants (
  system_cov_id   TEXT PRIMARY KEY,
  deal_id         TEXT NOT NULL,
  covenant_id     TEXT NOT NULL,
  tested_value    REAL,
  compliance_status TEXT,
  updated_at      TEXT NOT NULL
);

CREATE TABLE system_pricing (
  deal_id         TEXT PRIMARY KEY,
  rate_bps        INTEGER NOT NULL,
  fee_bps         INTEGER NOT NULL,
  updated_at      TEXT NOT NULL
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

-- Live customer + archived duplicate sharing normalized TIN idea
INSERT INTO customers VALUES
 ('CIF-417', 'Northgate Logistics LLC', '94-3177119',
  'cfo@northgate.example', 'active', '2026-01-20T00:00:00Z'),
 ('CIF-092', 'Northgate Logistics, LLC', '943177119',
  'ap@northgate.example', 'archived', '2023-06-01T00:00:00Z'),
 ('CIF-631', 'Cascade Precision Inc', '91-5550100',
  'treasurer@cascade.example', 'active', '2025-11-01T00:00:00Z');

INSERT INTO credit_products VALUES
 ('REV-STD', 'revolving_credit', 'Standard Revolver', 'active', 275, 25),
 ('REV-OLD', 'revolving_credit', 'Legacy Revolver', 'matured', 325, 40),
 ('TL-STD', 'term_loan', 'Standard Term Loan', 'active', 300, 30);

INSERT INTO covenants VALUES
 ('COV-LEV', 'REV-STD', 'LEVERAGE', '<=', 4.0, 'active'),
 ('COV-OLD', 'REV-OLD', 'LEVERAGE', '<=', 3.5, 'retired'),
 ('COV-TL', 'TL-STD', 'DSCR', '>=', 1.25, 'active');
