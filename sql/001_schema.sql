-- Enterprise Multi-Tenant Financial Ledger Schema
-- Models high-volume OLTP postings + regulatory & operational reporting workloads.

DROP TABLE IF EXISTS ledger_entries CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;

CREATE TABLE accounts (
    account_id       BIGSERIAL PRIMARY KEY,
    tenant_id        INTEGER NOT NULL,
    account_number   VARCHAR(32) NOT NULL UNIQUE,
    customer_segment VARCHAR(16) NOT NULL CHECK (customer_segment IN ('RETAIL', 'SME', 'CORPORATE', 'TREASURY')),
    currency         CHAR(3) NOT NULL DEFAULT 'INR',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE ledger_entries (
    entry_id        BIGSERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL,
    account_id      BIGINT NOT NULL REFERENCES accounts(account_id),
    status          VARCHAR(16) NOT NULL CHECK (status IN ('SETTLED', 'PENDING', 'FAILED', 'REVERSED')),
    txn_type        VARCHAR(16) NOT NULL CHECK (txn_type IN ('CREDIT', 'DEBIT', 'FEE', 'REFUND')),
    amount_cents    BIGINT NOT NULL,
    fee_cents       INTEGER NOT NULL DEFAULT 0,
    reference_code  VARCHAR(40) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE ledger_entries IS
    'Append-only enterprise ledger table populated in chronological created_at order for realistic BRIN correlation.';