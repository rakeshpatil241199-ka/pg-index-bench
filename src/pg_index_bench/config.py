"""Environment-driven configuration for PostgreSQL connections and benchmarks."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class DBConfig:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "pg_index_bench"
    user: str = "bench_user"
    password: str = "bench_secret"

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )

    @classmethod
    def from_env(cls) -> "DBConfig":
        return cls(
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            dbname=os.getenv("PGDATABASE", "pg_index_bench"),
            user=os.getenv("PGUSER", "bench_user"),
            password=os.getenv("PGPASSWORD", "bench_secret"),
        )


@dataclass(frozen=True)
class BenchmarkConfig:
    accounts: int = 25_000
    ledger_rows: int = 1_000_000
    warmup_runs: int = 2
    iterations: int = 10
    seed: int = 20210319
    sql_dir: Path = Path(__file__).resolve().parents[2] / "sql"

    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        return cls(
            accounts=int(os.getenv("BENCH_ACCOUNTS", "25000")),
            ledger_rows=int(os.getenv("BENCH_LEDGER_ROWS", "1000000")),
            warmup_runs=int(os.getenv("BENCH_WARMUP_RUNS", "2")),
            iterations=int(os.getenv("BENCH_ITERATIONS", "10")),
            seed=int(os.getenv("BENCH_SEED", "20210319")),
        )