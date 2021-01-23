"""Command-line entry point for pg-index-bench."""

import argparse
import json
from pathlib import Path
import sys

from pg_index_bench.config import BenchmarkConfig, DBConfig
from pg_index_bench.db import execute_sql_file
from pg_index_bench.generator import seed_database
from pg_index_bench.reporter import render_markdown_report, save_reports
from pg_index_bench.runner import run_profile_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pg-index-bench",
        description="Automated PostgreSQL 15 indexing & EXPLAIN (ANALYZE, BUFFERS) benchmark suite.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-schema", help="Create accounts and ledger_entries tables.")

    seed_cmd = sub.add_parser("seed", help="Populate synthetic enterprise ledger dataset via COPY.")
    seed_cmd.add_argument("--accounts", type=int, default=None, help="Number of accounts to generate.")
    seed_cmd.add_argument("--rows", type=int, default=None, help="Number of ledger rows to generate.")
    seed_cmd.add_argument("--seed", type=int, default=None, help="PRNG seed for reproducibility.")

    run_cmd = sub.add_parser("run", help="Run a single profile (baseline or optimized).")
    run_cmd.add_argument("--profile", choices=["baseline", "optimized"], required=True)
    run_cmd.add_argument("--iterations", type=int, default=None)

    cmp_cmd = sub.add_parser("compare", help="Run baseline vs optimized suites and emit comparison report.")
    cmp_cmd.add_argument("--iterations", type=int, default=None)
    cmp_cmd.add_argument("--output-dir", default="./reports", help="Directory to write JSON and Markdown reports.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db_cfg = DBConfig.from_env()
    bench_cfg = BenchmarkConfig.from_env()

    if args.command == "init-schema":
        execute_sql_file(db_cfg, bench_cfg.sql_dir / "001_schema.sql")
        print("Initialized PostgreSQL schema successfully.")
        return 0

    if args.command == "seed":
        accounts = args.accounts or bench_cfg.accounts
        rows = args.rows or bench_cfg.ledger_rows
        seed = args.seed or bench_cfg.seed
        stats = seed_database(db_cfg, num_accounts=accounts, num_ledger_rows=rows, seed=seed)
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "run":
        if args.iterations is not None:
            bench_cfg = BenchmarkConfig(
                accounts=bench_cfg.accounts,
                ledger_rows=bench_cfg.ledger_rows,
                warmup_runs=bench_cfg.warmup_runs,
                iterations=args.iterations,
                seed=bench_cfg.seed,
                sql_dir=bench_cfg.sql_dir,
            )
        report = run_profile_suite(db_cfg, bench_cfg, profile=args.profile)
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "compare":
        if args.iterations is not None:
            bench_cfg = BenchmarkConfig(
                accounts=bench_cfg.accounts,
                ledger_rows=bench_cfg.ledger_rows,
                warmup_runs=bench_cfg.warmup_runs,
                iterations=args.iterations,
                seed=bench_cfg.seed,
                sql_dir=bench_cfg.sql_dir,
            )
        print("Running baseline profile (no secondary indexes)...")
        baseline = run_profile_suite(db_cfg, bench_cfg, profile="baseline")
        print("Running optimized profile (B-Tree, Composite, INCLUDE, Partial, GIN, BRIN)...")
        optimized = run_profile_suite(db_cfg, bench_cfg, profile="optimized")

        paths = save_reports(baseline, optimized, Path(args.output_dir))
        print("\n" + render_markdown_report(baseline, optimized))
        print(f"Reports saved to: {paths['markdown']} and {paths['json']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))