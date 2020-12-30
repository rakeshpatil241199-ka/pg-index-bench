-- Optimized PostgreSQL 15 Indexing Strategy
-- Demonstrates targeted index selection across OLTP, semi-structured JSONB, and reporting queries.

-- 1. Composite B-Tree on accounts for tenant + segment filtering
CREATE INDEX IF NOT EXISTS idx_accounts_tenant_segment
    ON accounts (tenant_id, customer_segment);

-- 2. Composite B-Tree matching equality prefix (tenant_id, account_id) + range/sort (created_at DESC)
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_acct_created
    ON ledger_entries (tenant_id, account_id, created_at DESC);

-- 3. Covering B-Tree with INCLUDE payload enabling Index-Only Scans for Q2 aggregations
CREATE INDEX IF NOT EXISTS idx_ledger_covering_summary
    ON ledger_entries (tenant_id, account_id, created_at)
    INCLUDE (amount_cents, fee_cents, status);

-- 4. Partial B-Tree indexing only active PENDING entries (~1.8% of total table rows)
CREATE INDEX IF NOT EXISTS idx_ledger_pending_partial
    ON ledger_entries (tenant_id, created_at DESC)
    WHERE status = 'PENDING' AND amount_cents > 0;

-- 5. GIN index on JSONB metadata for @> containment predicates
CREATE INDEX IF NOT EXISTS idx_ledger_metadata_gin
    ON ledger_entries USING GIN (metadata);

-- 6. GIN index on TEXT[] tags for multi-tag array containment queries
CREATE INDEX IF NOT EXISTS idx_ledger_tags_gin
    ON ledger_entries USING GIN (tags);

-- 7. BRIN index on append-only created_at for minimal-footprint time-window scans
CREATE INDEX IF NOT EXISTS idx_ledger_created_brin
    ON ledger_entries USING BRIN (created_at)
    WITH (pages_per_range = 128);