import tempfile
import unittest
from pathlib import Path

from fold_lm.v05_benchmarks.gate_e_c132_process_case import evaluate_case


class V05C132ProcessFencingTests(unittest.TestCase):
    def test_two_process_resolved_case_has_one_current_write(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            row = evaluate_case(root_path / "f.sqlite", root_path / "case", "r1", 2, "RESOLVED")
            self.assertTrue(row["passed"])
            self.assertEqual(row["winner_count"], 1)
            self.assertEqual(row["current_accepts"], 1)
            self.assertEqual(row["stale_accepts"], 0)

    def test_two_process_unknown_case_stores_no_effect(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            row = evaluate_case(root_path / "f.sqlite", root_path / "case", "r2", 2, "UNKNOWN")
            self.assertTrue(row["passed"])
            self.assertEqual(row["current_accepts"], 0)
            self.assertEqual(row["stale_accepts"], 0)
            self.assertTrue(row["stored_none"])


if __name__ == "__main__":
    unittest.main()
