-- Q6: Multi-Table Enterprise Reporting Join (Composite + Array GIN target)
-- Joins corporate accounts against high-value tagged ledger entries.
SELECT
    a.customer_segment,
    a.currency,
    COUNT(*) AS high_value_txns,
    SUM(l.amount_cents) AS total_amount_cents
FROM ledger_entries l
JOIN accounts a ON a.account_id = l.account_id
WHERE l.tags @> ARRAY['high-value', 'sla-priority']::text[]
  AND a.tenant_id = 5
GROUP BY a.customer_segment, a.currency
ORDER BY total_amount_cents DESC;