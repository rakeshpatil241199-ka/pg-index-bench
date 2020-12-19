-- Q4: Compliance Risk Audit over Semi-Structured Metadata (GIN JSONB target)
-- Uses containment operator @> to locate flagged NEFT transfers.
SELECT
    entry_id,
    tenant_id,
    account_id,
    amount_cents,
    metadata->>'region' AS region,
    created_at
FROM ledger_entries
WHERE metadata @> '{"channel": "NEFT", "risk_flag": true}'::jsonb
ORDER BY created_at DESC
LIMIT 100;