-- Q1: Point-in-time Account Statement Lookup (Composite B-Tree target)
-- Fetches recent ledger activity for a specific tenant and account within a 90-day window.
SELECT
    entry_id,
    status,
    txn_type,
    amount_cents,
    reference_code,
    created_at
FROM ledger_entries
WHERE tenant_id = 7
  AND account_id = 1007
  AND created_at >= TIMESTAMPTZ '2020-09-01 00:00:00+00'
  AND created_at <  TIMESTAMPTZ '2020-12-01 00:00:00+00'
ORDER BY created_at DESC
LIMIT 50;