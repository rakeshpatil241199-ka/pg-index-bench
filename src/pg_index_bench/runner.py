"""Automated benchmark orchestrator executing SQL suites under EXPLAIN (ANALYZE, BUFFERS)."""

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Any, Dict, List

from pg_index_bench.config import BenchmarkConfig, DBConfig
from pg_index_bench.db import (
    execute_sql_file,
    get_connection,
    get_storage_footprint,
    vacuum_analyze_tables,
)
from pg_index_bench.explain_parser import ExplainMetrics, parse_explain_json


def percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


@dataclass
class QueryBenchmarkSummary:
    query_name: str
    profile: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_planning_ms: float
    avg_shared_hit_blocks: float
    avg_shared_read_blocks: float
    buffer_hit_ratio_pct: float
    heap_fetches: int
    scan_types: List[str]
    indexes_used: List[str]
    actual_rows: int


def discover_queries(queries_dir: Path) -> List[Path]:
    return sorted(queries_dir.glob("*.sql"))


def benchmark_single_query(
    cfg: DBConfig,
    query_path: Path,
    profile: str,
    warmup_runs: int,
    iterations: int,
) -> QueryBenchmarkSummary:
    sql_body = query_path.read_text(encoding="utf-8").strip().rstrip(";")
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql_body};"

    samples: List[ExplainMetrics] = []
    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            for _ in range(warmup_runs):
                cur.execute(explain_sql)
                cur.fetchone()

            for _ in range(iterations):
                cur.execute(explain_sql)
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError(f"No EXPLAIN output returned for {query_path.name}")
                samples.append(parse_explain_json(row[0]))

    exec_times = sorted(m.execution_time_ms for m in samples)
    avg_plan = sum(m.planning_time_ms for m in samples) / len(samples)
    avg_hits = sum(m.shared_hit_blocks for m in samples) / len(samples)
    avg_reads = sum(m.shared_read_blocks for m in samples) / len(samples)
    total_blocks = avg_hits + avg_reads
    hit_ratio = 100.0 if total_blocks == 0 else round((avg_hits / total_blocks) * 100.0, 2)

    last = samples[-1]
    return QueryBenchmarkSummary(
        query_name=query_path.stem,
        profile=profile,
        iterations=iterations,
        p50_ms=round(percentile(exec_times, 50.0), 3),
        p95_ms=round(percentile(exec_times, 95.0), 3),
        p99_ms=round(percentile(exec_times, 99.0), 3),
        avg_planning_ms=round(avg_plan, 3),
        avg_shared_hit_blocks=round(avg_hits, 1),
        avg_shared_read_blocks=round(avg_reads, 1),
        buffer_hit_ratio_pct=hit_ratio,
        heap_fetches=last.heap_fetches,
        scan_types=last.scan_types,
        indexes_used=last.indexes_used,
        actual_rows=last.actual_rows,
    )


def run_profile_suite(
    db_cfg: DBConfig,
    bench_cfg: BenchmarkConfig,
    profile: str,
) -> Dict[str, Any]:
    if profile == "baseline":
        execute_sql_file(db_cfg, bench_cfg.sql_dir / "002_indexes_baseline.sql")
    elif profile == "optimized":
        execute_sql_file(db_cfg, bench_cfg.sql_dir / "003_indexes_optimized.sql")
    else:
        raise ValueError(f"Unsupported profile: {profile}")

    vacuum_analyze_tables(db_cfg)

    queries_dir = bench_cfg.sql_dir / "queries"
    results: List[Dict[str, Any]] = []
    for q_path in discover_queries(queries_dir):
        summary = benchmark_single_query(
            cfg=db_cfg,
            query_path=q_path,
            profile=profile,
            warmup_runs=bench_cfg.warmup_runs,
            iterations=bench_cfg.iterations,
        )
        results.append(asdict(summary))

    storage = get_storage_footprint(db_cfg)
    return {
        "profile": profile,
        "warmup_runs": bench_cfg.warmup_runs,
        "iterations": bench_cfg.iterations,
        "storage": storage,
        "queries": results,
    }