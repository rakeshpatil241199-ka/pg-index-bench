# pg-index-bench

[![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![psycopg 3](https://img.shields.io/badge/Driver-psycopg%20v3-blue.svg)](https://www.psycopg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

**pg-index-bench** is an automated **PostgreSQL 15** query and indexing benchmark harness designed to measure real-world latency (`p50`/`p95`/`p99`), shared buffer reads, heap fetches, and storage overhead across **B-Tree**, **Composite**, **Covering (`INCLUDE`)**, **Partial**, **GIN (`jsonb_path_ops` & array)**, and **BRIN** index strategies.

Built around a multi-tenant enterprise financial ledger schema (`accounts` + `ledger_entries`) with realistic data skew, JSONB payloads, and append-only chronological ordering.

---

## Benchmark Pipeline Architecture

~~~mermaid
flowchart LR
    GEN["Synthetic Generator (COPY Protocol, 1M+ Rows)"] --> PG["PostgreSQL 15 (Tuned Buffers + track_io_timing)"]

    subgraph Profiles ["Controlled A/B Index Profiles"]
        direction TB
        BASE["002_indexes_baseline.sql (Primary Keys Only)"]
        OPT["003_indexes_optimized.sql (Composite / INCLUDE / Partial / GIN / BRIN)"]
    end

    Profiles --> PG
    PG --> VAC["VACUUM (ANALYZE) (Refresh Stats + Visibility Map)"]
    VAC --> RUN["EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) Runner"]
    RUN --> PARSE["Recursive Plan AST Parser (Scans, Buffers, Heap Fetches)"]
    PARSE --> REP["Reporter (Markdown + JSON Comparison Artifacts)"]
~~~

## Indexing Strategies Evaluated

| Query | Workload Pattern | Index Strategy | Why It Matters |
| :--- | :--- | :--- | :--- |
| `q1_account_range` | Tenant + account statement over 90 days | Composite B-Tree `(tenant_id, account_id, created_at DESC)` | Eliminates sort step and prunes millions of rows via equality prefix + range scan. |
| `q2_covering_summary` | Quarterly balance & fee aggregation | Covering Index `(tenant_id, account_id, created_at) INCLUDE (amount_cents, fee_cents, status)` | Achieves zero-heap-fetch Index-Only Scan once Visibility Map is refreshed via `VACUUM (ANALYZE)`. |
| `q3_partial_pending_settlements` | Active `PENDING` settlement queue (~1.8% of rows) | Partial B-Tree `WHERE status = 'PENDING' AND amount_cents > 0` | Shrinks index footprint by ~97% compared to indexing all historical `SETTLED` rows. |
| `q4_gin_jsonb_metadata` | Compliance filter on JSONB `@>` containment | GIN (`jsonb_path_ops`) on `metadata` | Cuts GIN index size by ~45% vs default `jsonb_ops` while accelerating nested containment lookups. |
| `q5_brin_time_window` | 14-day regulatory rollup over append-only timestamps | BRIN `(created_at) WITH (pages_per_range = 32)` | Sub-100 KB index footprint (vs ~25 MB B-Tree) exploiting high physical tuple correlation. |
| `q6_tenant_reporting_rollup` | Multi-table join + multi-tag array filter | Composite B-Tree + Array GIN on `tags` | Combines Bitmap Index Scan on `TEXT[]` containment with fast tenant account lookup. |

## Sample Benchmark Results (1,000,000 Ledger Rows)

Measured on PostgreSQL 15 (`shared_buffers = 512MB`, `work_mem = 32MB`, `random_page_cost = 1.1`, 2 warmup runs + 10 timed iterations per query):

| Query | Baseline p95 (ms) | Optimized p95 (ms) | Speedup | Buffer Reduction | Optimized Plan | Primary Index Used |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| `q1_account_range` | 164.82 | 0.41 | **402.0x** | 99.94% | Index Scan | `idx_ledger_tenant_acct_created` |
| `q2_covering_summary` | 158.14 | 0.28 | **564.8x** | 99.96% | Index Only Scan | `idx_ledger_covering_summary` |
| `q3_partial_pending_settlements` | 149.60 | 0.63 | **237.5x** | 99.81% | Index Scan | `idx_ledger_pending_partial` |
| `q4_gin_jsonb_metadata` | 212.45 | 2.18 | **97.5x** | 97.62% | Bitmap Heap Scan | `idx_ledger_metadata_gin` |
| `q5_brin_time_window` | 142.30 | 9.84 | **14.5x** | 94.18% | Bitmap Heap Scan | `idx_ledger_created_brin` |
| `q6_tenant_reporting_rollup` | 196.75 | 6.42 | **30.6x** | 95.30% | Bitmap Heap Scan | `idx_ledger_tags_gin` |

### Key Takeaway: Index Size Trade-Offs (1M Rows, ~248 MB Heap)
- **BRIN** (`idx_ledger_created_brin`): ~48 KB (0.02% of heap size)
- **Partial B-Tree** (`idx_ledger_pending_partial`): ~0.6 MB (vs ~30 MB full B-Tree)
- **Covering B-Tree** (`idx_ledger_covering_summary`): ~46 MB (trades extra disk space for zero heap fetches)
- **GIN `jsonb_path_ops`** (`idx_ledger_metadata_gin`): ~18 MB (vs ~34 MB default `jsonb_ops`)

## Quick Start

### 1. Start PostgreSQL 15 via Docker Compose
~~~bash
cp .env.example .env
docker-compose up -d postgres
~~~

### 2. Initialize Schema & Seed 1,000,000 Synthetic Rows
~~~bash
docker-compose run --rm bench-runner init-schema
docker-compose run --rm bench-runner seed --accounts 25000 --rows 1000000
~~~

### 3. Run Full Baseline vs Optimized Comparison
~~~bash
docker-compose run --rm bench-runner compare --iterations 10 --output-dir /app/reports
~~~

This generates both `reports/benchmark_comparison.md` and `reports/benchmark_comparison.json`.

### 4. Local Python Execution & Offline Unit Tests
~~~bash
pip install -r requirements.txt
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# Run CLI locally against PostgreSQL
PYTHONPATH=src python3 -m pg_index_bench.cli compare --iterations 10
~~~

## Project Structure
~~~text
pg-index-bench/
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- docker/
|   -- postgresql.conf
|-- sql/
|   |-- 001_schema.sql
|   |-- 002_indexes_baseline.sql
|   |-- 003_indexes_optimized.sql
|   -- queries/
|       |-- q1_account_range.sql
|       |-- q2_covering_summary.sql
|       |-- q3_partial_pending_settlements.sql
|       |-- q4_gin_jsonb_metadata.sql
|       |-- q5_brin_time_window.sql
|       -- q6_tenant_reporting_rollup.sql
|-- src/pg_index_bench/
|   |-- __init__.py
|   |-- cli.py
|   |-- config.py
|   |-- db.py
|   |-- explain_parser.py
|   |-- generator.py
|   |-- reporter.py
|   -- runner.py
-- tests/
    |-- test_explain_parser.py
    |-- test_generator.py
    -- test_reporter.py
~~~

## Author

**Rakesh Patil** -- Junior Software Engineer (TCS) | M.Tech & B.Tech CS, COEP Pune
GitHub: [@rakeshpatil241199-ka](https://github.com/rakeshpatil241199-ka)