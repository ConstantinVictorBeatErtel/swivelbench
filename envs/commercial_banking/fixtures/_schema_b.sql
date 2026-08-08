-- ncino_core (system B)
CREATE TABLE customers (
  customer_id     TEXT PRIMARY KEY,
  legal_name      TEXT NOT NULL,
  tin             TEXT,
  contact_email   TEXT,
  record_status   TEXT NOT NULL,   -- active | archived
  updated_at      TEXT NOT NULL
);

CREATE TABLE credit_products (
  product_code    TEXT PRIMARY KEY,
  request_type    TEXT NOT NULL,
  name            TEXT NOT NULL,
  status          TEXT NOT NULL,   -- active | matured
  rate_bps        INTEGER NOT NULL,
  fee_bps         INTEGER NOT NULL
);

CREATE TABLE covenants (
  covenant_id     TEXT PRIMARY KEY,
  product_code    TEXT NOT NULL,
  covenant_type   TEXT NOT NULL,   -- LEVERAGE | DSCR | FCCR
  operator        TEXT NOT NULL,
  threshold       REAL NOT NULL,
  status          TEXT NOT NULL    -- active | retired
);

CREATE TABLE deals (
  deal_id         TEXT PRIMARY KEY,
  request_id      TEXT NOT NULL,
  customer_id     TEXT NOT NULL,
  product_code    TEXT NOT NULL,
  limit_amount    REAL NOT NULL,
  template_id     TEXT,
  status          TEXT NOT NULL,   -- draft | pushed
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
