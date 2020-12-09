"""Deterministic synthetic enterprise ledger generator using PostgreSQL COPY.

Rows are emitted in strictly increasing `created_at` timestamp order to mirror
append-only financial ledger ingestion and maintain high physical correlation
for BRIN index evaluation.
"""

from datetime import datetime, timedelta, timezone
import json
import random
import time
from typing import Dict, Iterator, List, Tuple

from pg_index_bench.config import DBConfig
from pg_index_bench.db import analyze_tables, get_connection

SEGMENTS = ("RETAIL", "SME", "CORPORATE", "TREASURY")
CURRENCIES = ("INR", "USD", "EUR", "GBP")
CHANNELS = ("UPI", "NEFT", "RTGS", "IMPS", "SWIFT", "CARD")
REGIONS = ("IN-MH", "IN-KA", "IN-DL", "IN-TN", "IN-GJ", "SG-01")
TXN_TYPES = ("CREDIT", "DEBIT", "FEE", "REFUND")
TAG_POOL = ("auto-recon", "kyc-verified", "high-value", "cross-border", "batch-eod", "sla-priority")

TENANT_COUNT = 25


def iter_account_rows(
    num_accounts: int, seed: int = 20210319
) -> Iterator[Tuple[int, str, str, str, datetime]]:
    rng = random.Random(seed)
    base_ts = datetime(2019, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(1, num_accounts + 1):
        tenant_id = ((i - 1) % TENANT_COUNT) + 1
        acct_num = f"ACCT-{tenant_id:02d}-{i:08d}"
        segment = rng.choices(SEGMENTS, weights=(55, 25, 15, 5), k=1)[0]
        currency = rng.choices(CURRENCIES, weights=(78, 12, 6, 4), k=1)[0]
        created_at = base_ts + timedelta(minutes=i * 3)
        yield (tenant_id, acct_num, segment, currency, created_at)


def iter_ledger_rows(
    num_rows: int,
    num_accounts: int,
    seed: int = 20210319,
    span_days: int = 365,
) -> Iterator[Tuple[int, int, str, str, int, int, str, str, List[str], datetime]]:
    """Yield realistic skewed enterprise ledger postings in monotonic time order.

    Status distribution intentionally leaves only ~1.8% of rows as PENDING so
    partial indexing demonstrates realistic index-size and scan selectivity gains.
    """
    rng = random.Random(seed + 101)
    start_ts = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    step_seconds = (span_days * 86400.0) / max(num_rows, 1)

    for idx in range(num_rows):
        account_id = rng.randint(1, num_accounts)
        tenant_id = ((account_id - 1) % TENANT_COUNT) + 1

        # Skewed status distribution: ~94.5% SETTLED, ~1.8% PENDING, ~2.2% FAILED, ~1.5% REVERSED
        roll = rng.random()
        if roll < 0.945:
            status = "SETTLED"
        elif roll < 0.963:
            status = "PENDING"
        elif roll < 0.985:
            status = "FAILED"
        else:
            status = "REVERSED"

        txn_type = rng.choices(TXN_TYPES, weights=(46, 46, 5, 3), k=1)[0]
        amount_cents = int(round(rng.lognormvariate(9.2, 1.35)))
        fee_cents = max(0, int(amount_cents * 0.0025)) if txn_type in ("DEBIT", "CREDIT") else 0
        ref_code = f"TXN{tenant_id:02d}{idx + 1:010d}"

        channel = rng.choices(CHANNELS, weights=(38, 22, 10, 15, 5, 10), k=1)[0]
        region = rng.choice(REGIONS)
        risk_flag = rng.random() < 0.025
        metadata = json.dumps(
            {
                "channel": channel,
                "region": region,
                "risk_flag": risk_flag,
                "batch_id": (idx // 5000) + 1,
            },
            separators=(",", ":"),
        )

        tags: List[str] = [TAG_POOL[0] if rng.random() < 0.7 else TAG_POOL[4]]
        if amount_cents > 500_000:
            tags.append("high-value")
        if risk_flag:
            tags.append("sla-priority")
        if channel == "SWIFT":
            tags.append("cross-border")

        created_at = start_ts + timedelta(seconds=idx * step_seconds)
        yield (
            tenant_id,
            account_id,
            status,
            txn_type,
            amount_cents,
            fee_cents,
            ref_code,
            metadata,
            tags,
            created_at,
        )


def seed_database(
    cfg: DBConfig,
    num_accounts: int,
    num_ledger_rows: int,
    seed: int = 20210319,
    batch_log_interval: int = 250_000,
) -> Dict[str, float]:
    """Stream synthetic rows directly into PostgreSQL via COPY protocol."""
    t0 = time.perf_counter()

    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ledger_entries, accounts RESTART IDENTITY CASCADE;")

            with cur.copy(
                "COPY accounts (tenant_id, account_number, customer_segment, currency, created_at) FROM STDIN"
            ) as copy:
                for row in iter_account_rows(num_accounts, seed=seed):
                    copy.write_row(row)

            inserted = 0
            with cur.copy(
                "COPY ledger_entries ("
                "tenant_id, account_id, status, txn_type, amount_cents, "
                "fee_cents, reference_code, metadata, tags, created_at"
                ") FROM STDIN"
            ) as copy:
                for row in iter_ledger_rows(num_ledger_rows, num_accounts, seed=seed):
                    copy.write_row(row)
                    inserted += 1
                    if batch_log_interval > 0 and inserted % batch_log_interval == 0:
                        elapsed = time.perf_counter() - t0
                        print(f"  [seed] inserted {inserted:,}/{num_ledger_rows:,} rows ({elapsed:.1f}s)")

    analyze_tables(cfg)
    total_sec = time.perf_counter() - t0
    return {
        "accounts": float(num_accounts),
        "ledger_rows": float(num_ledger_rows),
        "elapsed_sec": round(total_sec, 3),
        "rows_per_sec": round(num_ledger_rows / max(total_sec, 0.001), 1),
    }