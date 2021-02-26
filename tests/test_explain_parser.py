import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pg_index_bench.explain_parser import parse_explain_json


class TestExplainParser(unittest.TestCase):
    def test_parses_index_only_scan_with_zero_heap_fetches(self) -> None:
        sample = [
            {
                "Plan": {
                    "Node Type": "Aggregate",
                    "Total Cost": 42.15,
                    "Actual Rows": 3,
                    "Shared Hit Blocks": 12,
                    "Shared Read Blocks": 0,
                    "Plans": [
                        {
                            "Node Type": "Index Only Scan",
                            "Index Name": "idx_ledger_covering_summary",
                            "Heap Fetches": 0,
                            "Shared Hit Blocks": 12,
                            "Shared Read Blocks": 0,
                        }
                    ],
                },
                "Planning Time": 0.214,
                "Execution Time": 0.482,
            }
        ]

        metrics = parse_explain_json(sample)
        self.assertAlmostEqual(metrics.execution_time_ms, 0.482)
        self.assertAlmostEqual(metrics.planning_time_ms, 0.214)
        self.assertEqual(metrics.buffer_hit_ratio_pct, 100.0)
        self.assertEqual(metrics.heap_fetches, 0)
        self.assertEqual(metrics.scan_types, ["Index Only Scan"])
        self.assertEqual(metrics.indexes_used, ["idx_ledger_covering_summary"])

    def test_parses_bitmap_heap_scan_and_brin_lossy_blocks(self) -> None:
        sample = [
            {
                "Plan": {
                    "Node Type": "Bitmap Heap Scan",
                    "Total Cost": 3102.5,
                    "Actual Rows": 38400,
                    "Shared Hit Blocks": 750,
                    "Shared Read Blocks": 250,
                    "Exact Heap Blocks": 0,
                    "Lossy Heap Blocks": 1000,
                    "Plans": [
                        {
                            "Node Type": "Bitmap Index Scan",
                            "Index Name": "idx_ledger_created_brin",
                        }
                    ],
                },
                "Planning Time": 0.35,
                "Execution Time": 14.92,
            }
        ]

        metrics = parse_explain_json(sample)
        self.assertEqual(metrics.buffer_hit_ratio_pct, 75.0)
        self.assertEqual(metrics.lossy_heap_blocks, 1000)
        self.assertEqual(metrics.scan_types, ["Bitmap Heap Scan", "Bitmap Index Scan"])
        self.assertEqual(metrics.indexes_used, ["idx_ledger_created_brin"])

    def test_rejects_empty_payload(self) -> None:
        with self.assertRaises(ValueError):
            parse_explain_json([])


if __name__ == "__main__":
    unittest.main()