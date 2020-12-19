-- Q2: Account Quarterly Volume Aggregation (Covering Index INCLUDE -> Index-Only Scan target)
-- Selects only columns contained inside the index key + INCLUDE payload to avoid heap fetches.
SELECT
    status,
    COUNT(*) AS txn_count,
    SUM(amount_cents) AS gross_amount_cents,
    SUM(fee_cents) AS total_fee_cents
FROM ledger_entries
WHERE tenant_id = 7
  AND account_id = 1007
  AND created_at >= TIMESTAMPTZ '2020-07-01 00:00:00+00'
  AND created_at <  TIMESTAMPTZ '2020-10-01 00:00:00+00'
GROUP BY status;