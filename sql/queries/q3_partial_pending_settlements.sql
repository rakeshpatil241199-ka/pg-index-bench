-- Q3: Pending Settlement Queue (Partial Index target)
-- Targets the ~1.8% active PENDING slice without bloating index storage with SETTLED rows.
SELECT
    entry_id,
    account_id,
    amount_cents,
    reference_code,
    created_at
FROM ledger_entries
WHERE tenant_id = 12
  AND status = 'PENDING'
  AND amount_cents > 0
ORDER BY created_at DESC
LIMIT 100;