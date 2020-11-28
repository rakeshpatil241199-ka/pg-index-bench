"""PostgreSQL connection management, SQL execution, and catalog inspection."""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List

import psycopg
from psycopg.rows import dict_row

from pg_index_bench.config import DBConfig


@contextmanager
def get_connection(cfg: DBConfig, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(cfg.dsn, autocommit=autocommit)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def execute_sql_file(cfg: DBConfig, sql_path: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)


def analyze_tables(cfg: DBConfig) -> None:
    with get_connection(cfg, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("ANALYZE accounts;")
            cur.execute("ANALYZE ledger_entries;")


def get_storage_footprint(cfg: DBConfig) -> Dict[str, Any]:
    """Query pg_relation_size / pg_indexes_size for ledger_entries and each index."""
    table_sql = """
        SELECT
            pg_relation_size('ledger_entries') AS heap_bytes,
            pg_indexes_size('ledger_entries') AS total_index_bytes,
            pg_total_relation_size('ledger_entries') AS total_bytes,
            (SELECT reltuples::bigint FROM pg_class WHERE relname = 'ledger_entries') AS est_rows
    """
    idx_sql = """
        SELECT
            indexrelid::regclass::text AS index_name,
            pg_relation_size(indexrelid) AS index_bytes,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_stat_user_indexes
        WHERE relname = 'ledger_entries'
        ORDER BY pg_relation_size(indexrelid) DESC
    """
    with get_connection(cfg) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(table_sql)
            table_row = dict(cur.fetchone() or {})
            cur.execute(idx_sql)
            indexes: List[Dict[str, Any]] = [dict(r) for r in cur.fetchall()]
    return {"table": table_row, "indexes": indexes}