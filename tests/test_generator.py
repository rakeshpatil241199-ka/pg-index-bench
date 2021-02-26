import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pg_index_bench.generator import iter_account_rows, iter_ledger_rows


class TestSyntheticGenerator(unittest.TestCase):
    def test_ledger_rows_have_monotonic_timestamps_and_realistic_skew(self) -> None:
        rows = list(iter_ledger_rows(num_rows=4000, num_accounts=500, seed=1234))
        self.assertEqual(len(rows), 4000)

        timestamps = [r[9] for r in rows]
        self.assertEqual(timestamps, sorted(timestamps))

        pending_count = sum(1 for r in rows if r[2] == "PENDING")
        pending_ratio = pending_count / len(rows)
        self.assertGreater(pending_ratio, 0.005)
        self.assertLess(pending_ratio, 0.05)

        meta = json.loads(rows[0][7])
        self.assertIn("channel", meta)
        self.assertIn("risk_flag", meta)

    def test_account_generation_is_deterministic(self) -> None:
        run_a = list(iter_account_rows(50, seed=99))
        run_b = list(iter_account_rows(50, seed=99))
        self.assertEqual(run_a, run_b)


if __name__ == "__main__":
    unittest.main()