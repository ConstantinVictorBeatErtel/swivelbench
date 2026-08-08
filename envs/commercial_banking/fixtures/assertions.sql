-- Assertions for CB-SEED-001. Ground truth:
-- template TPL-REV-OK, digest DIG-CUR, leverage 3.7590, customer CIF-417,
-- product REV-STD, rate 275 / fee 25, LEVERAGE compliant.
--
-- Rubric metadata (Maximum Viable Atomicity):
--   step=  workflow step id (S1..S7)
--   level= tool|plan|adapt|ground|reason  (Hierarchy of Agentic Capabilities)
--   role=  required|bonus|penalty
-- File-format checks (F1/F2) live in core/format_check.py.

-- ===== Step: choose report template =====
-- @assert id=P1 kind=positive weight=1.0 step=S1_template level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM a.request_state
  WHERE request_id = 'CRQ-1001' AND selected_template_id = 'TPL-REV-OK'
);

-- @assert id=N1 kind=negative weight=1.0 step=S1_template level=adapt role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM a.request_state
  WHERE request_id = 'CRQ-1001' AND selected_template_id = 'TPL-REV-BAD'
);

-- @assert id=T1 kind=trail weight=1.0 step=S1_template level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'select_template' AND target_key = 'TPL-REV-OK'
);

-- ===== Step: pull products / covenants / prior deals =====
-- @assert id=P5 kind=positive weight=1.0 step=S6_customer_push level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = 'CRQ-1001' AND customer_id = 'CIF-417'
    AND product_code = 'REV-STD' AND status = 'pushed'
    AND ABS(limit_amount - 2500000.0) < 1e-6
);

-- @assert id=P10 kind=positive weight=1.0 step=S6_customer_push level=plan role=required
SELECT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = 'CRQ-1001' AND template_id = 'TPL-REV-OK'
    AND status = 'pushed'
);

-- @assert id=N3 kind=negative weight=1.0 step=S6_customer_push level=adapt role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = 'CRQ-1001' AND product_code = 'REV-OLD'
);

-- @assert id=T9 kind=trail weight=1.0 step=S2_products level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'search_prior_deals'
);

-- @assert id=T10 kind=trail weight=1.0 step=S2_products level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'list_covenants' AND target_key = 'REV-STD'
);

-- ===== Step: digests → Excel model =====
-- @assert id=P2 kind=positive weight=1.0 step=S3_model level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM a.model_cells mc
  JOIN a.request_state rs ON rs.model_id = mc.model_id
  WHERE rs.request_id = 'CRQ-1001' AND mc.cell_key = 'leverage'
    AND ABS(mc.cell_value - 3.7590) < 1e-9
);

-- @assert id=P6 kind=positive weight=1.0 step=S3_model level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = 'CRQ-1001' AND em.digest_id = 'DIG-CUR'
);

-- @assert id=P7 kind=positive weight=1.0 step=S3_model level=ground role=required
SELECT (
  SELECT COUNT(*) FROM a.model_cells mc
  JOIN a.request_state rs ON rs.model_id = mc.model_id
  JOIN a.excel_models em ON em.model_id = rs.model_id
  JOIN a.web_digests d ON d.digest_id = em.digest_id
  WHERE rs.request_id = 'CRQ-1001' AND em.digest_id = 'DIG-CUR'
    AND (
      (mc.cell_key = 'revenue' AND ABS(mc.cell_value - d.revenue) < 1e-6)
      OR (mc.cell_key = 'ebitda' AND ABS(mc.cell_value - d.ebitda) < 1e-6)
      OR (mc.cell_key = 'total_debt' AND ABS(mc.cell_value - d.total_debt) < 1e-6)
      OR (mc.cell_key = 'interest_expense'
          AND ABS(mc.cell_value - d.interest_expense) < 1e-6)
      OR (mc.cell_key = 'leverage' AND ABS(mc.cell_value - 3.7590) < 1e-9)
    )
) = 5;

-- @assert id=N6 kind=negative weight=1.0 step=S3_model level=reason role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = 'CRQ-1001' AND em.digest_id = 'DIG-STALE'
);

-- @assert id=N7 kind=negative weight=1.0 step=S3_model level=adapt role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM a.excel_models em
  JOIN a.request_state rs ON rs.model_id = em.model_id
  WHERE rs.request_id = 'CRQ-1001' AND em.digest_id = 'DIG-CONFLICT'
);

-- @assert id=T6 kind=trail weight=1.0 step=S3_model level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'create_model' AND target_key LIKE 'MDL-%'
);

-- ===== Step: spreading team + check =====
-- @assert id=P3 kind=positive weight=1.0 step=S4_spreading level=plan role=required
SELECT EXISTS (
  SELECT 1 FROM a.spread_jobs
  WHERE request_id = 'CRQ-1001' AND status = 'checked'
);

-- @assert id=P9 kind=positive weight=1.0 step=S4_spreading level=adapt role=required
SELECT EXISTS (
  SELECT 1 FROM a.spread_lines sl
  JOIN a.spread_jobs sj ON sj.job_id = sl.job_id
  WHERE sj.request_id = 'CRQ-1001' AND sl.line_key = 'ebitda'
    AND sl.corrected = 1
    AND ABS(sl.line_value - 4150000.0) < 1e-6
);

-- @assert id=X3 kind=propagation weight=1.0 step=S4_spreading level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM a.spread_lines sl
  JOIN a.spread_jobs sj ON sj.job_id = sl.job_id
  WHERE sj.request_id = 'CRQ-1001' AND sl.line_key = 'ebitda'
    AND ABS(sl.line_value - 4150000.0) < 1e-6
);

-- @assert id=X4 kind=propagation weight=1.0 step=S4_spreading level=ground role=required
SELECT NOT EXISTS (
  SELECT 1
  FROM a.spread_jobs sj
  JOIN a.spread_lines sl ON sl.job_id = sj.job_id
  JOIN a.model_cells mc ON mc.model_id = sj.model_id AND mc.cell_key = sl.line_key
  WHERE sj.request_id = 'CRQ-1001' AND sj.status = 'checked'
    AND ABS(sl.line_value - mc.cell_value) > 1e-6
);

-- @assert id=N5 kind=negative weight=1.0 step=S4_spreading level=plan role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals d
  JOIN a.spread_jobs sj ON sj.request_id = d.request_id
  WHERE d.request_id = 'CRQ-1001' AND d.status = 'pushed'
    AND sj.status != 'checked'
);

-- @assert id=T2 kind=trail weight=1.0 step=S4_spreading level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'check_spread' AND target_key LIKE 'SPJ-%'
);

-- @assert id=T7 kind=trail weight=1.0 step=S4_spreading level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'submit_spreading' AND target_key LIKE 'SPJ-%'
);

-- ===== Step: write report sections =====
-- @assert id=P4 kind=positive weight=1.0 step=S5_report level=plan role=required
SELECT (
  SELECT COUNT(*) FROM a.report_sections
  WHERE request_id = 'CRQ-1001' AND template_id = 'TPL-REV-OK'
) = 4;

-- @assert id=P8 kind=positive weight=1.0 step=S5_report level=ground role=required
SELECT (
  SELECT COUNT(*) FROM a.report_sections
  WHERE request_id = 'CRQ-1001' AND template_id = 'TPL-REV-OK'
    AND section_title IN (
      'Executive Summary', 'Financial Analysis',
      'Covenant Review', 'Recommendation')
) = 4;

-- @assert id=X5 kind=propagation weight=1.0 step=S5_report level=ground role=required
SELECT NOT EXISTS (
  SELECT 1 FROM a.report_sections rs
  JOIN a.request_state st ON st.request_id = rs.request_id
  WHERE rs.request_id = 'CRQ-1001'
    AND rs.template_id != st.selected_template_id
);

-- @assert id=N4 kind=negative weight=1.0 step=S5_report level=adapt role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM a.report_sections
  WHERE request_id = 'CRQ-1001' AND template_id = 'TPL-REV-BAD'
);

-- @assert id=T8 kind=trail weight=1.0 step=S5_report level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'write_report' AND target_key = 'CRQ-1001'
);

-- ===== Step: resolve customer + push nCino =====
-- @assert id=N2 kind=negative weight=1.0 step=S6_customer_push level=adapt role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM b.deals
  WHERE request_id = 'CRQ-1001' AND customer_id = 'CIF-092'
);

-- @assert id=T3 kind=trail weight=1.0 step=S6_customer_push level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'push_deal' AND target_key LIKE 'DEAL-%'
);

-- @assert id=T5 kind=trail weight=1.0 step=S6_customer_push level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'customer_resolved' AND target_key = 'CIF-417'
);

-- ===== Step: update covenants + pricing =====
-- @assert id=X1 kind=propagation weight=1.0 step=S7_systems level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM b.system_pricing sp
  JOIN b.deals d ON d.deal_id = sp.deal_id
  WHERE d.request_id = 'CRQ-1001' AND sp.rate_bps = 275 AND sp.fee_bps = 25
);

-- @assert id=X2 kind=propagation weight=1.0 step=S7_systems level=ground role=required
SELECT EXISTS (
  SELECT 1 FROM b.system_covenants sc
  JOIN b.deals d ON d.deal_id = sc.deal_id
  WHERE d.request_id = 'CRQ-1001' AND sc.covenant_id = 'COV-LEV'
    AND ABS(sc.tested_value - 3.7590) < 1e-9
    AND sc.compliance_status = 'compliant'
);

-- @assert id=N8 kind=negative weight=1.0 step=S7_systems level=reason role=penalty
SELECT NOT EXISTS (
  SELECT 1 FROM b.system_covenants sc
  JOIN b.deals d ON d.deal_id = sc.deal_id
  WHERE d.request_id = 'CRQ-1001' AND sc.covenant_id = 'COV-OLD'
);

-- @assert id=T4 kind=trail weight=1.0 step=S7_systems level=tool role=required
SELECT EXISTS (
  SELECT 1 FROM b.audit_log
  WHERE action = 'update_systems'
);
