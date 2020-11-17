-- Baseline profile: drops all secondary indexes, retaining only Primary Keys
-- and the accounts(account_number) UNIQUE constraint so baseline measurements
-- capture unindexed Sequential Scan / Parallel Seq Scan behavior.

DROP INDEX IF EXISTS idx_accounts_tenant_segment;
DROP INDEX IF EXISTS idx_ledger_tenant_acct_created;
DROP INDEX IF EXISTS idx_ledger_covering_summary;
DROP INDEX IF EXISTS idx_ledger_pending_partial;
DROP INDEX IF EXISTS idx_ledger_metadata_gin;
DROP INDEX IF EXISTS idx_ledger_tags_gin;
DROP INDEX IF EXISTS idx_ledger_created_brin;