import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pg_index_bench.reporter import compute_comparison, render_markdown_report, save_reports
from pg_index_bench.runner import percentile


class TestReporter(unittest.TestCase):
    def test_percentile_interpolation(self) -> None:
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.assertAlmostEqual(percentile(vals, 50.0), 30.0)
        self.assertAlmostEqual(percentile(vals, 95.0), 48.0)

    def test_comparison_and_markdown_rendering(self) -> None:
        baseline = {
            "profile": "baseline",
            "storage": {"table": {"heap_bytes": 262144000, "total_index_bytes": 22020096}, "indexes": []},
            "queries": [
                {
                    "query_name": "q1_account_range",
                    "p95_ms": 182.4,
                    "avg_shared_hit_blocks": 20000.0,
                    "avg_shared_read_blocks": 12000.0,
                    "scan_types": ["Seq Scan"],
                    "indexes_used": [],
                }
            ],
        }
        optimized = {
            "profile": "optimized",
            "storage": {
                "table": {"heap_bytes": 262144000, "total_index_bytes": 96468992},
                "indexes": [{"index_name": "idx_ledger_tenant_acct_created", "index_bytes": 33554432, "idx_scan": 12}],
            },
            "queries": [
                {
                    "query_name": "q1_account_range",
                    "p95_ms": 0.72,
                    "avg_shared_hit_blocks": 14.0,
                    "avg_shared_read_blocks": 0.0,
                    "scan_types": ["Index Scan"],
                    "indexes_used": ["idx_ledger_tenant_acct_created"],
                }
            ],
        }

        diff = compute_comparison(baseline, optimized)
        self.assertEqual(len(diff), 1)
        self.assertGreater(diff[0]["speedup_x"], 200.0)
        self.assertGreater(diff[0]["block_reduction_pct"], 99.9)

        md = render_markdown_report(baseline, optimized)
        self.assertIn("q1_account_range", md)
        self.assertIn("idx_ledger_tenant_acct_created", md)

        with tempfile.TemporaryDirectory() as td:
            paths = save_reports(baseline, optimized, Path(td))
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["markdown"].exists())


if __name__ == "__main__":
    unittest.main()