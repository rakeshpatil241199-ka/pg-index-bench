-- Q5: Regulatory 14-Day Compliance Rollup (BRIN append-only timestamp target)
-- Aggregates a narrow chronological slice over physically correlated heap pages.
SELECT
    txn_type,
    status,
    COUNT(*) AS entries,
    SUM(amount_cents) AS total_volume_cents
FROM ledger_entries
WHERE created_at >= TIMESTAMPTZ '2020-11-15 00:00:00+00'
  AND created_at <  TIMESTAMPTZ '2020-11-29 00:00:00+00'
GROUP BY txn_type, status
ORDER BY total_volume_cents DESC;